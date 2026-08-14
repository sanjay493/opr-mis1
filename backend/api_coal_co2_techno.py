"""
API endpoints for the Coal Consumption & CO2/Water/PM Environmental
Performance Indicators (EPI) report — see
techno_project/coal_co2_epi_extractor.py for the PDF parsing itself and its
module docstring for the source report's layout.

Unlike every other techno-entry extractor (one file -> one plant), this
report covers all 5 plants (BSP, DSP, RSP, BSL, ISP) in a single PDF, so
there's no `plant` form field — preview/insert both operate on all 5 at
once. It also carries an FY-annual target column (constant across whichever
month's report you upload), written to techno_plan_fy alongside the
per-plant monthly actuals in techno_data.

Flow (mirrors /api/mcr-techno's tentative-data safeguard):
  1. POST /preview — extract for all 5 plants + FY targets; flags any
     parameter that would overwrite an existing techno_data value.
  2. POST /insert  — MERGE the (optionally trimmed) records into
     techno_data (per plant, unit='General') and techno_plan_fy (per
     plant + SAIL). 409s on conflicts unless confirm_replace=true.
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


def _target_fy(report_month: str) -> str:
    year, mon = int(report_month[:4]), int(report_month[5:7])
    fy = year if mon >= 4 else year - 1
    return f"{fy}-{(fy + 1) % 100:02d}"


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


@router.post("/preview")
async def preview_coal_co2(
    file: UploadFile = File(..., description="Coal Consumption & CO2/Water/PM EPI report (.pdf or .docx)"),
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

        enviro, coal = blob["enviro"], blob["coal"]

        plant_records = []
        for plant in PLANTS:
            month_json = plant_techno_json(enviro, coal, plant)
            till_json = plant_till_techno_json(enviro, plant)
            plant_records.append({"plant": plant, "unit": "General",
                                   "techno_json": {"month": month_json, "till_month": till_json}})

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

        init_db()
        conflicts = _existing_conflicts(report_month, plant_records)
        total_params = sum(
            sum(1 for v in r["techno_json"]["month"].values() if v is not None)
            for r in plant_records
        )

        return {
            "status": "preview",
            "report_month": report_month,
            "source_file": file.filename or "",
            "plants": plant_records,
            "targets": targets,
            "total_params": total_params,
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
async def insert_coal_co2(payload: dict):
    """
    Body: { report_month, source_file, plants: [{plant, unit, techno_json}],
            targets: {fy, <plant>: {<param label>: {value, unit}}, ...},
            confirm_replace: bool }

    plants[] merges into techno_data (unit='General') per plant. targets
    (if present) merges into techno_plan_fy per plant + SAIL, keyed by
    targets.fy.
    """
    report_month = payload.get("report_month", "")
    source_file = payload.get("source_file", "")
    plant_records = payload.get("plants", [])
    targets = payload.get("targets") or {}
    confirm_replace = bool(payload.get("confirm_replace"))

    _validate_month(report_month)
    if not plant_records:
        raise HTTPException(status_code=400, detail="No plant records to insert")

    init_db()
    conflicts = _existing_conflicts(report_month, plant_records)
    if conflicts and not confirm_replace:
        summary = "; ".join(f"{c['plant']} ({len(c['params'])} params)" for c in conflicts)
        raise HTTPException(
            status_code=409,
            detail=(
                f"{report_month} already has values for: {summary}. "
                "Confirm to overwrite with the newly extracted figures."
            ),
        )

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
        "replaced_existing": bool(conflicts),
    }
