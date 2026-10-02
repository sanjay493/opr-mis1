"""
API endpoints for the "Coal OMI" Excel report — see
techno_project/coal_omi_extractor.py for the parsing itself and its module
docstring for the source workbook's layout.

Saves two kinds of techno_data rows:
  - unit="Coal_Consumption", one per plant + SAIL: the full as-printed
    OIS-1 row (hard/soft/pcc/mcc, CDI coal, totals and blend %), month and
    till_month verbatim from the workbook. This is the single stored copy
    of coal consumption.
  - unit="Coal_Receipt_Stock", SAIL only: receipt plan/actual, consumption
    actual/average, and opening stock (OIS-2).

Until 2026-10-02 the upload also wrote the same 4 tonnages again under
unit="General" (indigenous_pcc/indigenous_mcc/imported_hard_coal/
imported_soft_coal), a duplicate of Coal_Consumption's pcc/mcc/hard/soft
that confused the techno manual-entry form. It no longer does. Months
saved before then still hold those General keys, so readers
(page_key_parameters.py, page_at_a_glance.py, the /data-entry/coal-
consumption viewer) prefer Coal_Consumption and fall back to General.

The preview still returns per-plant + SAIL rows for those 4 keys
("plants"/"sail") as a review table: month from the workbook, till_month
the workbook's own printed cumulative, and a computed SAIL sum of the 5
plants cross-checked against the printed SAIL row. They are display-only
and never saved.

Flow (mirrors /api/coal-co2's preview/insert/conflict pattern):
  1. POST /preview — extract, compute the SAIL sum, cross-check it against
     the report's own printed SAIL row (flagged in validation_warnings, not
     blocking), flag any existing techno_data overlap.
  2. POST /insert — MERGE the (optionally trimmed) records into techno_data.
     409s on conflicts unless confirm_replace=true.
"""

import os
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

_TP_DIR = str(Path(__file__).parent / "techno_project")
if _TP_DIR not in sys.path:
    sys.path.insert(0, _TP_DIR)

from coal_omi_extractor import (  # noqa: E402
    PLANTS, COAL_KEY_UNITS, extract_coal_omi,
)

_COAL_CONSUMPTION_UNIT = "Coal_Consumption"
from db import init_db, merge_upsert_techno_data, get_techno_data  # noqa: E402
from api_unified_techno import _validate_month  # noqa: E402

router = APIRouter(prefix="/api/coal-omi", tags=["coal-omi"])

_SAIL_TOLERANCE = 0.02          # '000 T — printed values are already rounded to 3dp


def _existing_conflicts(report_month: str, records: list) -> list:
    """Records whose extracted parameters already hold a value in
    techno_data for this month (checked per record's own unit, not always
    "General" — Coal_Receipt_Stock needs the same check)."""
    conflicts = []
    for rec in records:
        existing = get_techno_data(rec["plant"], report_month, unit=rec.get("unit", "General"))
        existing_month = (existing.get(rec.get("unit", "General")) or {}).get("month", {})
        overlap = [
            k for k, v in rec["techno_json"]["month"].items()
            if v is not None and existing_month.get(k) is not None
        ]
        if overlap:
            conflicts.append({"plant": rec["plant"], "unit": rec.get("unit", "General"), "params": overlap})
    return conflicts


def _build_plant_records(ois1: dict, report_month: str):
    """-> (plant_records[5], sail_record, validation_warnings[])
    Display-only review rows for the 4 coal keys (never saved - see the
    module docstring): month from the workbook, till_month the workbook's
    own printed cumulative. SAIL month is the computed sum of the 5 plants,
    cross-checked against the printed SAIL row."""
    warnings = []
    plant_records = []
    sail_month_computed = {k: 0.0 for k in COAL_KEY_UNITS}

    for plant in PLANTS:
        month_vals = ois1[plant]["month"]
        for key, v in month_vals.items():
            if v is not None:
                sail_month_computed[key] += v
        till_vals = {k: v for k, v in ois1[plant]["report_cumulative"].items() if v is not None}
        plant_records.append({
            "plant": plant, "unit": "General",
            "techno_json": {"month": month_vals, "till_month": till_vals},
        })

    sail_reported_month = ois1.get("SAIL", {}).get("month", {})
    for key, computed in sail_month_computed.items():
        reported = sail_reported_month.get(key)
        if reported is not None and abs(computed - reported) > _SAIL_TOLERANCE:
            warnings.append({
                "type": "sail_mismatch", "key": key,
                "computed": round(computed, 3), "reported": reported,
                "diff": round(computed - reported, 3),
            })

    sail_till = {k: v for k, v in ois1.get("SAIL", {}).get("report_cumulative", {}).items() if v is not None}
    sail_record = {
        "plant": "SAIL", "unit": "General",
        "techno_json": {
            "month": {k: round(v, 3) for k, v in sail_month_computed.items()},
            "till_month": sail_till,
        },
    }

    return plant_records, sail_record, warnings


def _build_ois1_detail_records(ois1_detail: dict) -> list:
    """One record per plant + SAIL, unit="Coal_Consumption" — the full
    as-printed OIS-1 row (see extract_ois1_detail), stored verbatim for the
    "Consumption of Coking Coal and CDI Coal" display page to render
    directly with no recomputation."""
    return [
        {
            "plant": plant, "unit": _COAL_CONSUMPTION_UNIT,
            "techno_json": {"month": detail["month"], "till_month": detail["till_month"]},
        }
        for plant, detail in ois1_detail.items()
    ]


def _build_ois2_record(ois2: dict) -> dict:
    r, c, s = ois2["receipt"], ois2["consumption"], ois2["stock"]
    month_json = {
        "receipt_plan_indigenous": r["indigenous"]["plan"], "receipt_actual_indigenous": r["indigenous"]["actual"],
        "receipt_plan_imported": r["imported"]["plan"], "receipt_actual_imported": r["imported"]["actual"],
        "receipt_plan_total": r["total"]["plan"], "receipt_actual_total": r["total"]["actual"],
        "consumption_actual_indigenous": c["indigenous"]["actual"], "consumption_avg_indigenous": c["indigenous"]["avg"],
        "consumption_actual_imported": c["imported"]["actual"], "consumption_avg_imported": c["imported"]["avg"],
        "consumption_actual_total": c["total"]["actual"], "consumption_avg_total": c["total"]["avg"],
        "stock_indigenous": s["indigenous"], "stock_imported": s["imported"], "stock_total": s["total"],
        "stock_as_of_month": s["as_of_month"],
    }
    # Every month this same upload's OIS-2 sheet also carries stock data
    # for (a rolling multi-month view, not just report_month's own
    # column) — see extract_ois2/_extract_stock_history. Read by
    # page_coal_receipts_stock.py across ALL uploaded months' own
    # records, not just each FY month's own single-point one, so one
    # upload can backfill several FY months' stock at once. Omitted
    # entirely (rather than sent as {}) when extraction found nothing, so
    # merge_upsert_techno_data's non-null-wins merge never wipes out a
    # richer history a previous upload already stored here.
    stock_history = ois2.get("stock_history")
    if stock_history:
        month_json["stock_history"] = stock_history
    return {"plant": "SAIL", "unit": "Coal_Receipt_Stock", "techno_json": {"month": month_json}}


@router.post("/preview")
async def preview_coal_omi(
    file: UploadFile = File(..., description="Coal OMI report (.xlsx)"),
    report_month: str = Form(..., description="Selected month YYYY-MM — must match the workbook's own month"),
):
    _validate_month(report_month)

    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await file.read())
        tmp.close()

        try:
            blob = extract_coal_omi(tmp.name, report_month)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        init_db()
        plant_records, sail_record, warnings = _build_plant_records(blob["ois1"], report_month)
        ois2_record = _build_ois2_record(blob["ois2"])
        detail_records = _build_ois1_detail_records(blob["ois1_detail"])

        saved_records = [ois2_record] + detail_records
        conflicts = _existing_conflicts(report_month, saved_records)
        total_params = sum(
            sum(1 for v in r["techno_json"]["month"].values() if v is not None)
            for r in saved_records
        )

        return {
            "status": "preview",
            "report_month": report_month,
            "source_file": file.filename or "",
            "plants": plant_records,
            "sail": sail_record,
            "ois2": ois2_record,
            "detail": detail_records,
            "total_params": total_params,
            "validation_warnings": warnings,
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


@router.post("/insert")
async def insert_coal_omi(payload: dict):
    """
    Body: { report_month, source_file, ois2: {...},
            detail: [{plant,unit,techno_json}], confirm_replace: bool }
    "plants"/"sail" from the preview may still be sent; they're display-only
    and ignored here (see the module docstring).
    """
    report_month = payload.get("report_month", "")
    source_file = payload.get("source_file", "")
    ois2_record = payload.get("ois2")
    detail_records = payload.get("detail", [])
    confirm_replace = bool(payload.get("confirm_replace"))

    _validate_month(report_month)
    all_records = []
    if ois2_record:
        all_records.append(ois2_record)
    all_records.extend(detail_records)
    if not all_records:
        raise HTTPException(status_code=400, detail="No records to insert")

    init_db()
    conflicts = _existing_conflicts(report_month, all_records)
    if conflicts and not confirm_replace:
        summary = "; ".join(f"{c['plant']}/{c['unit']} ({len(c['params'])} params)" for c in conflicts)
        raise HTTPException(
            status_code=409,
            detail=(
                f"{report_month} already has values for: {summary}. "
                "Confirm to overwrite with the newly extracted figures."
            ),
        )

    saved = []
    for rec in all_records:
        try:
            merge_upsert_techno_data(
                plant=rec["plant"], report_month=report_month, unit=rec.get("unit", "General"),
                new_techno_json=rec["techno_json"], source_file=source_file,
            )
            saved.append(f"{rec['plant']}/{rec.get('unit', 'General')}")
        except Exception as e:
            print(f"Warning: Could not save {rec.get('plant')}/{rec.get('unit')}: {e}")

    return {
        "status": "ok",
        "report_month": report_month,
        "source_file": source_file,
        "saved": saved,
        "replaced_existing": bool(conflicts),
    }


@router.post("/opening-stock")
async def save_opening_stock(payload: dict):
    """Manual entry for a single month's Coking Coal opening stock
    (Indigenous/Imported/Total, '000 T) — the same three techno_data keys
    /preview + /insert write from the Coal OMI workbook's OIS-2 sheet (see
    _build_ois2_record), but reachable without needing that month's own
    workbook on hand. Lets a month be filled in (or corrected) directly, so
    page_coal_receipts_stock.py's 4-FY opening-stock-history tables can be
    backfilled for months whose source workbook isn't available.

    Body: { report_month, stock_indigenous, stock_imported, stock_total }
    (any of the three may be omitted/null to leave that figure untouched).
    """
    report_month = payload.get("report_month", "")
    _validate_month(report_month)

    month_fields = {}
    for key in ("stock_indigenous", "stock_imported", "stock_total"):
        v = payload.get(key)
        if v is not None:
            month_fields[key] = float(v)
    if not month_fields:
        raise HTTPException(status_code=400, detail="Provide at least one of stock_indigenous/stock_imported/stock_total.")

    merge_upsert_techno_data(
        plant="SAIL", report_month=report_month, unit="Coal_Receipt_Stock",
        new_techno_json={"month": month_fields}, source_file="manual-entry",
    )
    return {"status": "ok", "report_month": report_month, "saved": month_fields}
