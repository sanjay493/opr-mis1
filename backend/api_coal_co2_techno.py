"""
API endpoints for the CO2/Water/PM Environmental Performance Indicators
(EPI) report — see techno_project/coal_co2_epi_extractor.py for the PDF/
docx/xlsx parsing itself and its module docstring for the source report's
layout and formats. Coal Consumption is NOT handled here — see
techno_project/coal_omi_extractor.py (api_coal_omi_techno.py), the
dedicated higher-precision extractor for that data, so the two never write
the same techno_data field for the same plant/month.

Unlike every other techno-entry extractor (one file -> one plant), this
report covers all 5 plants (BSP, DSP, RSP, BSL, ISP) in a single upload, so
there's no `plant` form field — preview/insert both operate on all 5 at
once. It also carries an FY-annual target column (constant across whichever
month's report you upload), written to techno_plan_fy alongside the
per-plant monthly actuals in techno_data.

Some source formats (extract_xlsx, the newer "Major EPIs" .docx) also print
a Comparable-Prior-Year (CPLY) column alongside the current month — the
same calendar month, one year earlier, plus its own FY-cumulative. /preview
surfaces that as a second, independent record set (`cply`) the caller can
choose to submit to /insert or not; the two are never merged automatically.

Flow (mirrors /api/mcr-techno's tentative-data safeguard):
  1. POST /preview — extract for all 5 plants + FY targets (+ CPLY, when
     the report carries it); for every extracted value, includes whatever
     techno_data already holds for that plant/param/month so the caller can
     show a before/after comparison, not just a conflict flag.
  2. POST /insert  — MERGE the (optionally trimmed) records into
     techno_data (per plant, unit='General') and techno_plan_fy (per
     plant + SAIL). 409s on conflicts unless confirm_replace=true. Pass a
     `cply` block (same shape as the main `report_month`/`plants`) to also
     save the CPLY month's figures in the same call.
"""

import os
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

_TP_DIR = str(Path(__file__).parent / "techno_project")
if _TP_DIR not in sys.path:
    sys.path.insert(0, _TP_DIR)

from coal_co2_epi_extractor import (  # noqa: E402
    PLANTS, ENVIRO_PARAM_ORDER, ENVIRO_KEY_UNITS,
    extract_report, mlabel_from_report_month, plant_techno_json, plant_till_techno_json,
)
from db import (  # noqa: E402
    init_db, merge_upsert_techno_data, get_techno_data,
    get_techno_plant_plan, save_techno_plant_plan,
    get_sail_techno_plan, save_sail_techno_plan,
)
from api_unified_techno import _validate_month  # noqa: E402

router = APIRouter(prefix="/api/coal-co2", tags=["coal-co2-epi"])

_ALL_KEYS = [json_key for _key, _label, json_key in ENVIRO_PARAM_ORDER]


def _target_fy(report_month: str) -> str:
    year, mon = int(report_month[:4]), int(report_month[5:7])
    fy = year if mon >= 4 else year - 1
    return f"{fy}-{(fy + 1) % 100:02d}"


def _existing_values(plant: str, report_month: str) -> dict:
    """-> {"month": {json_key: value|None}, "till_month": {...}} — whatever
    techno_data (unit='General') already holds for every param this
    extractor writes, regardless of whether this month's upload extracted a
    value for it. Used so /preview can show an Extracted-vs-Existing
    comparison, not just flag an overlap."""
    existing = get_techno_data(plant, report_month, unit="General").get("General") or {}
    existing_month = existing.get("month") or {}
    existing_till = existing.get("till_month") or {}
    return {
        "month": {k: existing_month.get(k) for k in _ALL_KEYS},
        "till_month": {k: existing_till.get(k) for k in _ALL_KEYS},
    }


def _build_plant_records(enviro: dict) -> list:
    """-> [{plant, unit, techno_json: {month, till_month}, existing: {month, till_month}}, ...]"""
    records = []
    for plant in PLANTS:
        month_json = plant_techno_json(enviro, plant)
        till_json = plant_till_techno_json(enviro, plant)
        records.append({
            "plant": plant, "unit": "General",
            "techno_json": {"month": month_json, "till_month": till_json},
        })
    return records


def _existing_conflicts(report_month: str, plant_records: list) -> list:
    """Plants whose extracted parameters already hold a value in techno_data
    (unit='General') for this month."""
    conflicts = []
    for rec in plant_records:
        existing = get_techno_data(rec["plant"], report_month, unit="General")
        existing_month = (existing.get("General") or {}).get("month", {})
        overlap = [
            k for k, v in rec["techno_json"]["month"].items()
            if v is not None and existing_month.get(k) is not None
        ]
        if overlap:
            conflicts.append({"plant": rec["plant"], "params": overlap})
    return conflicts


def _sail_reported(enviro: dict) -> dict:
    """-> {"month": {json_key: value}, "till_month": {...}} — the report's
    own SAIL row, for display/cross-check only. Never part of `plants` (not
    saved - see module docstring: SAIL is deliberately never written to
    techno_data here, since the at-a-glance/major-techno pages compute it
    themselves as a Crude-Steel-weighted average across plants instead of
    trusting the report's own SAIL row)."""
    return {
        "month": plant_techno_json(enviro, "SAIL"),
        "till_month": plant_till_techno_json(enviro, "SAIL"),
    }


def _month_group_preview(report_month: str, enviro: dict) -> dict:
    plant_records = _build_plant_records(enviro)
    for rec in plant_records:
        rec["existing"] = _existing_values(rec["plant"], report_month)

    conflicts = _existing_conflicts(report_month, plant_records)
    total_params = sum(
        sum(1 for v in r["techno_json"]["month"].values() if v is not None)
        for r in plant_records
    )
    return {
        "report_month": report_month,
        "plants": plant_records,
        "sail": _sail_reported(enviro),
        "total_params": total_params,
        "has_existing": bool(conflicts),
        "existing_conflicts": conflicts,
    }


@router.post("/preview")
async def preview_coal_co2(
    file: UploadFile = File(..., description="CO2/Water/PM EPI report (.pdf, .docx or .xlsx)"),
    report_month: str = Form(..., description="Selected month YYYY-MM — must match a column in the report"),
):
    _validate_month(report_month)
    mlabel = mlabel_from_report_month(report_month)

    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await file.read())
        tmp.close()

        try:
            blob = extract_report(tmp.name, report_month, mlabel)
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Could not find a '{mlabel}' column in this report — "
                       f"check the selected month matches the uploaded file. ({e})",
            )

        enviro = blob["enviro"]
        init_db()
        main = _month_group_preview(report_month, enviro)

        target_fy = _target_fy(report_month)
        targets = {"fy": target_fy}
        for plant in PLANTS + ["SAIL"]:
            plant_targets = {}
            for key, label, jk in ENVIRO_PARAM_ORDER:
                v = enviro.get(key, {}).get("target", {}).get(plant)
                if v is not None:
                    plant_targets[label] = {"value": v, "unit": ENVIRO_KEY_UNITS[jk]}
            if plant_targets:
                targets[plant] = plant_targets

        cply = None
        if blob.get("cply"):
            cply = _month_group_preview(blob["cply"]["report_month"], blob["cply"]["enviro"])

        return {
            "status": "preview",
            "source_file": file.filename or "",
            "targets": targets,
            "cply": cply,
            **main,
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


def _save_month_group(report_month: str, plant_records: list, source_file: str) -> list:
    """Merges plant_records into techno_data for report_month, with no
    conflict check of its own — callers must resolve conflicts (via
    _existing_conflicts + confirm_replace) across every group being saved
    in the same call BEFORE calling this for any of them, so a 409 on one
    group never leaves another group's save half-applied.
    -> list of plants actually saved."""
    if not plant_records:
        return []
    saved_plants = []
    for rec in plant_records:
        try:
            merge_upsert_techno_data(
                plant=rec["plant"], report_month=report_month, unit=rec.get("unit", "General"),
                new_techno_json=rec["techno_json"], source_file=source_file,
            )
            saved_plants.append(rec["plant"])
        except Exception as e:
            print(f"Warning: Could not save {rec.get('plant')}: {e}")
    return saved_plants


@router.post("/insert")
async def insert_coal_co2(payload: dict):
    """
    Body: { report_month, source_file, plants: [{plant, unit, techno_json}],
            targets: {fy, <plant>: {<param label>: {value, unit}}, ...},
            cply: {report_month, plants: [...]} | omitted,
            confirm_replace: bool }

    plants[] merges into techno_data (unit='General') per plant. targets
    (if present) merges into techno_plan_fy per plant + SAIL, keyed by
    targets.fy. cply (if present — only when /preview returned one, i.e.
    the uploaded report carries a Comparable-Prior-Year column) is saved
    the same way, under its own report_month, in the same call.
    confirm_replace governs both the main and cply saves; a 409 from
    either aborts the whole call so nothing is saved half-confirmed.
    """
    report_month = payload.get("report_month", "")
    source_file = payload.get("source_file", "")
    plant_records = payload.get("plants", [])
    targets = payload.get("targets") or {}
    cply = payload.get("cply") or None
    cply_report_month = cply.get("report_month") if cply else None
    cply_records = (cply.get("plants") or []) if cply else []
    confirm_replace = bool(payload.get("confirm_replace"))

    _validate_month(report_month)
    if not plant_records:
        raise HTTPException(status_code=400, detail="No plant records to insert")
    if cply_records:
        _validate_month(cply_report_month)

    init_db()
    conflicts = _existing_conflicts(report_month, plant_records)
    cply_conflicts = _existing_conflicts(cply_report_month, cply_records) if cply_records else []
    if (conflicts or cply_conflicts) and not confirm_replace:
        parts = [f"{c['plant']} ({len(c['params'])} params)" for c in conflicts]
        cply_parts = [f"{c['plant']} ({len(c['params'])} params, {cply_report_month})" for c in cply_conflicts]
        summary = "; ".join(parts + cply_parts)
        raise HTTPException(
            status_code=409,
            detail=(
                f"{report_month} already has values for: {summary}. "
                "Confirm to overwrite with the newly extracted figures."
            ),
        )

    saved_plants = _save_month_group(report_month, plant_records, source_file)
    replaced_existing = bool(conflicts)
    cply_saved_plants = _save_month_group(cply_report_month, cply_records, source_file) if cply_records else []

    saved_targets = []
    target_fy = targets.get("fy")
    if target_fy:
        for plant, param_map in targets.items():
            if plant == "fy" or not param_map:
                continue
            if plant == "SAIL":
                plan = get_sail_techno_plan(target_fy)
                plan_data = dict(plan.get("data") or {})
                plan_data.update(param_map)
                save_sail_techno_plan(target_fy, plan_data,
                                       is_user_supplied=plan.get("is_user_supplied", False),
                                       created_by="coal_co2_epi_upload")
            else:
                plan = get_techno_plant_plan(plant, target_fy)
                plan_data = dict(plan.get("data") or {})
                plan_data.update(param_map)
                save_techno_plant_plan(plant, target_fy, plan_data,
                                        is_user_supplied=plan.get("is_user_supplied", False),
                                        created_by="coal_co2_epi_upload")
            saved_targets.append(plant)

    return {
        "status": "ok",
        "report_month": report_month,
        "source_file": source_file,
        "plants_saved": saved_plants,
        "targets_saved": saved_targets,
        "replaced_existing": replaced_existing,
        "cply_report_month": cply_report_month,
        "cply_plants_saved": cply_saved_plants,
    }
