"""
API endpoints for month-end MCR techno data (tentative for-the-month values).

Supported plants (see _EXTRACTORS):
  DSP — MCR techno page (Report_format/MONTHEND/mcr1_*.xlsx)
  BSP — MIS-2 and PPC MIS workbooks (auto-detected from file content)
  RSP — Daily Morning Report generated on the month-end date
  ISP — MORNING REPORT workbook generated on the month-end date

Flow (mirrors /api/techno but with two extra safeguards):
  1. POST /preview     — extract + verify C1 report date against the selected
                         month; returns records enriched with current DB values
                         and a has_existing flag.
  2. POST /cumulative  — optional: fill till_month for the previewed records
                         using the shared cumulative rules (techno_cumulative).
  3. POST /insert      — MERGE records into techno_data. Because MCR data is
                         tentative, if any extracted parameter already has a
                         value in the DB the call fails with 409 unless
                         confirm_replace=true (user consent).
"""

import os
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

# Make techno_project importable
_TP_DIR = str(Path(__file__).parent / "techno_project")
if _TP_DIR not in sys.path:
    sys.path.insert(0, _TP_DIR)

from dsp_mcr_techno_extractor import DspMcrTechnoExtractor, McrMonthMismatch  # noqa: E402
from bsp_monthend_techno_extractor import BspMonthendTechnoExtractor  # noqa: E402
from rsp_monthend_techno_extractor import RspMonthendTechnoExtractor  # noqa: E402
from isp_monthend_techno_extractor import IspMonthendTechnoExtractor  # noqa: E402
from db import (  # noqa: E402
    init_db, merge_upsert_techno_data, get_techno_data,
    enrich_techno_records_with_db,
)
from api_unified_techno import validate_units_for_plant, _validate_month  # noqa: E402
from techno_cumulative import compute_cumulative_preview  # noqa: E402

router = APIRouter(prefix="/api/mcr-techno", tags=["mcr-techno"])

_EXTRACTORS = {
    "DSP": DspMcrTechnoExtractor,
    "BSP": BspMonthendTechnoExtractor,  # auto-detects MIS-2 vs PPC MIS
    "RSP": RspMonthendTechnoExtractor,  # Daily Morning Report (month-end)
    "ISP": IspMonthendTechnoExtractor,  # MORNING REPORT (month-end)
}


def _get_extractor(plant: str):
    cls = _EXTRACTORS.get(plant.upper())
    if cls is None:
        raise HTTPException(
            status_code=400,
            detail=f"Month-end MCR extraction not supported for '{plant}'. "
                   f"Supported: {', '.join(sorted(_EXTRACTORS))}",
        )
    return cls


def _existing_conflicts(plant: str, report_month: str, records):
    """Units whose extracted parameters already hold a value in the DB."""
    existing = get_techno_data(plant, report_month)
    conflicts = []
    for rec in records:
        db_month = existing.get(rec.get("unit"), {}).get("month", {})
        overlap = [
            k for k, v in rec.get("techno_json", {}).get("month", {}).items()
            if v is not None and db_month.get(k) is not None
        ]
        if overlap:
            conflicts.append({"unit": rec["unit"], "params": overlap})
    return conflicts


@router.post("/preview")
async def preview_mcr_techno(
    plant: str = Form("DSP", description="Plant (currently only DSP)"),
    file: UploadFile = File(..., description="Month-end MCR techno page (.xlsx)"),
    report_month: str = Form(..., description="Selected month YYYY-MM — verified against the report's C1 date"),
):
    """Extract for-the-month techno values from the MCR report, without saving."""
    _validate_month(report_month)
    ExtractorClass = _get_extractor(plant)

    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await file.read())
        tmp.close()

        extractor = ExtractorClass(tmp.name, report_month=report_month)
        try:
            records = extractor.extract()
        except McrMonthMismatch as e:
            raise HTTPException(status_code=422, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        preview_records = [
            {"unit": rec["unit"], "techno_json": rec["techno_json"]}
            for rec in records
        ]
        total_params = sum(
            sum(1 for v in r["techno_json"].get("month", {}).values() if v is not None)
            for r in preview_records
        )

        init_db()
        enrich_techno_records_with_db(preview_records, plant, report_month)
        conflicts = _existing_conflicts(plant, report_month, preview_records)

        return {
            "status": "preview",
            "plant": plant,
            "report_month": report_month,
            "report_date": extractor.report_date.isoformat() if extractor.report_date else None,
            "source_file": file.filename or "",
            "units_extracted": len(preview_records),
            "total_params": total_params,
            "records": preview_records,
            "warnings": extractor.warnings,
            "has_existing": bool(conflicts),
            "existing_conflicts": conflicts,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@router.post("/cumulative")
async def calc_cumulative(payload: dict):
    """
    Fill till_month for previewed records using the shared cumulative rules
    (April → report_month, techno_cumulative.compute_cumulative_preview).
    Nothing is written to the DB here — records are the in-memory preview
    rows from a prior /preview call; the DB write only happens later, via
    /insert, when the user confirms.

    Body:    { plant, report_month, records: [{unit, techno_json}] }
    Returns: { records, computed, warnings, details } — records have
             till_month filled where a cumulative could be computed;
             warnings explain the rest. details = the same per-parameter
             calculation breakdown as /cumulative-all (method, production
             weights, month-by-month rows, formula steps) so the UI can show
             a "calculation step window" instead of silently filling the
             Cumulative column.
    """
    plant = (payload.get("plant") or "").upper()
    report_month = payload.get("report_month", "")
    records = payload.get("records", [])

    _validate_month(report_month)
    if not records:
        raise HTTPException(status_code=400, detail="No records to calculate")

    init_db()
    computed = 0
    warnings = []
    details = []
    for rec in records:
        unit = rec.get("unit", "")
        tj = rec.get("techno_json", {})
        month_vals = tj.get("month", {})
        till = tj.setdefault("till_month", {})
        # Unsaved production from the same payload serves as this month's
        # weight for the unit-wise weighted rules (e.g. furnace coke rate).
        current_production = month_vals.get("production")
        for key, val in month_vals.items():
            if val is None:
                continue
            try:
                result = compute_cumulative_preview(
                    plant, unit, key, report_month, current_value=val,
                    current_production=current_production,
                )
                details.append({
                    "unit": unit,
                    "param_key": key,
                    "method": result["method"],
                    "weight_item": result["weight_item"],
                    "rows": result["rows"],
                    "steps": result["steps"],
                    "warnings": result["warnings"],
                    "result": result["result"],
                    "previous_till_month": till.get(key),
                })
                till[key] = result["result"]
                computed += 1
            except ValueError as e:
                warnings.append(f"{unit} · {key}: {e}")

    return {
        "status": "ok",
        "plant": plant,
        "report_month": report_month,
        "records": records,
        "computed": computed,
        "warnings": warnings,
        "details": details,
    }


@router.post("/cumulative-all")
async def calc_cumulative_all(payload: dict):
    """
    Compute the April→month cumulative for every parameter of every unit
    already stored in techno_data for a plant+month — the bulk version of the
    techno-manual page's per-field "Calculate Cumulative" (same rules engine:
    techno_cumulative.compute_cumulative_preview). SAVES unless preview=true.

    Body:    { plant, report_month, overwrite: bool (default true),
               preview: bool (default false) }
             overwrite=false only fills till_month values that are empty.
             preview=true computes and returns the full per-parameter
             breakdown (method, production weights used, month-by-month
             rows, formula steps) WITHOUT writing anything to the DB, so the
             UI can show a "calculation step window" for the user to review
             before confirming the write (re-call with preview=false, or
             omitted, to actually save).
    Returns: { units, computed, skipped, warnings, details, preview }
             details = [{unit, param_key, method, weight_item, rows, steps,
                         warnings, result, previous_till_month}, ...]
    """
    plant = (payload.get("plant") or "").upper()
    report_month = payload.get("report_month", "")
    overwrite = payload.get("overwrite", True)
    preview = bool(payload.get("preview", False))

    _validate_month(report_month)
    if not plant:
        raise HTTPException(status_code=400, detail="plant is required")

    init_db()
    existing = get_techno_data(plant, report_month)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"No techno data found for {plant} {report_month} — "
                   "extract or enter month values first.",
        )

    computed = 0
    skipped = 0
    warnings = []
    units_updated = []
    details = []
    for unit, tj in existing.items():
        month_vals = tj.get("month", {})
        till = dict(tj.get("till_month", {}))
        current_production = month_vals.get("production")
        if not isinstance(current_production, (int, float)):
            current_production = None
        changed = False
        for key, val in month_vals.items():
            if not isinstance(val, (int, float)):
                continue   # null or non-numeric (e.g. 'HH:MM' times)
            if not overwrite and till.get(key) is not None:
                skipped += 1
                continue
            try:
                result = compute_cumulative_preview(
                    plant, unit, key, report_month, current_value=val,
                    current_production=current_production,
                )
                details.append({
                    "unit": unit,
                    "param_key": key,
                    "method": result["method"],
                    "weight_item": result["weight_item"],
                    "rows": result["rows"],
                    "steps": result["steps"],
                    "warnings": result["warnings"],
                    "result": result["result"],
                    "previous_till_month": tj.get("till_month", {}).get(key),
                })
                if result["result"] is not None:
                    till[key] = result["result"]
                    computed += 1
                    changed = True
            except ValueError as e:
                warnings.append(f"{unit} · {key}: {e}")
        if changed:
            units_updated.append(unit)
            if not preview:
                merge_upsert_techno_data(
                    plant=plant, report_month=report_month, unit=unit,
                    new_techno_json={"month": {}, "till_month": till},
                    source_file="cumulative_calc",
                )

    return {
        "status": "ok",
        "preview": preview,
        "details": details,
        "plant": plant,
        "report_month": report_month,
        "units": units_updated,
        "computed": computed,
        "skipped": skipped,
        "warnings": warnings,
    }


@router.post("/insert")
async def insert_mcr_techno(payload: dict):
    """
    Merge previously-previewed MCR records into techno_data.

    Body: { plant, report_month, source_file, records: [{unit, techno_json}],
            confirm_replace: bool }

    Uses merge semantics: only the extracted (non-null) parameters are
    written; parameters from other sources (e.g. the DSP monthly PDF) are
    kept. If any extracted parameter would replace an existing DB value and
    confirm_replace is not true, responds 409 so the UI can ask for consent.
    """
    plant = payload.get("plant", "")
    report_month = payload.get("report_month", "")
    source_file = payload.get("source_file", "")
    records = payload.get("records", [])
    confirm_replace = bool(payload.get("confirm_replace"))

    _validate_month(report_month)
    if not records:
        raise HTTPException(status_code=400, detail="No records to insert")
    validate_units_for_plant(plant, (rec.get("unit", "") for rec in records))

    init_db()
    conflicts = _existing_conflicts(plant, report_month, records)
    if conflicts and not confirm_replace:
        summary = "; ".join(
            f"{c['unit']} ({len(c['params'])} params)" for c in conflicts
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"{plant} {report_month} already has values for: {summary}. "
                "MCR data is tentative — existing values will be replaced. "
                "Confirm to proceed."
            ),
        )

    saved_count = 0
    for rec in records:
        try:
            merge_upsert_techno_data(
                plant=plant,
                report_month=report_month,
                unit=rec["unit"],
                new_techno_json=rec["techno_json"],
                source_file=source_file,
            )
            saved_count += 1
        except Exception as e:
            print(f"Warning: Could not save {rec.get('unit')}: {e}")

    sail_calc_status = "pending"
    try:
        from page_techno import calculate_and_store_sail_actuals
        sail_result = calculate_and_store_sail_actuals(report_month)
        sail_calc_status = "completed" if sail_result["success"] else "failed"
    except Exception as e:
        sail_calc_status = "error"
        print(f"⚠ Error auto-calculating SAIL: {e}")

    return {
        "status": "ok",
        "plant": plant,
        "report_month": report_month,
        "source_file": source_file,
        "units_extracted": len(records),
        "units_saved": saved_count,
        "units": [rec["unit"] for rec in records],
        "replaced_existing": bool(conflicts),
        "sail_actuals": sail_calc_status,
    }
