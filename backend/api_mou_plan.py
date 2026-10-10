"""
API endpoints for the MoU month-wise production target workbook — see
excel_extractors/excel_extractor_mou_plan.py for the parsing and the
workbook layout. Same preview/insert/conflict flow as /api/power-omi:
  1. POST /preview — extract (no DB writes), flag values already stored.
  2. POST /insert — upsert into mou_plan_table; 409 on existing values
     unless confirm_replace=true.
"""
import os
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

sys.path.insert(0, str(Path(__file__).parent / "excel_extractors"))
from excel_extractor_mou_plan import extract_mou_plan  # noqa: E402

import db  # noqa: E402
from page4 import PAGE4_ITEMS  # noqa: E402

router = APIRouter(prefix="/api/mou-plan", tags=["mou-plan"])


def _existing_conflicts(records: list) -> list:
    conn = db.connect()
    cur = conn.cursor()
    conflicts = []
    try:
        for rec in records:
            cur.execute(
                "SELECT month_actual FROM mou_plan_table "
                "WHERE report_month = ? AND plant_name = ? AND item_name = ?",
                (rec["report_month"], rec["plant_name"], rec["item_name"]),
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                conflicts.append(rec)
    finally:
        conn.close()
    return conflicts


def sail_set_warnings(records: list) -> list:
    """Warn about non-zero targets for plants that page 4 leaves out of an
    item's SAIL total (e.g. VISL Pig Iron). The extractor already checks the
    file's SAIL row against the sum of all its plant rows, so with no such
    plants the report's SAIL row equals the workbook's."""
    sail_sets = {cfg["db_item"]: set(cfg.get("sail_set", [])) for cfg in PAGE4_ITEMS}
    outside = {}
    for rec in records:
        members = sail_sets.get(rec["item_name"])
        if members is not None and rec["plant_name"] not in members and rec["value"]:
            outside.setdefault((rec["item_name"], rec["plant_name"]), []).append(rec["report_month"])
    return [
        f"{item} {plant}: non-zero MoU target in {len(months)} month(s), but the report's SAIL total "
        f"for {item} does not include {plant}, so it will be lower than the workbook's SAIL row."
        for (item, plant), months in sorted(outside.items())
    ]


@router.post("/preview")
async def preview_mou_plan(file: UploadFile = File(..., description="MoU plan workbook (.xlsx)")):
    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await file.read())
        tmp.close()
        try:
            result = extract_mou_plan(tmp.name)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        conflicts = _existing_conflicts(result["records"])
        return {
            "status": "preview",
            "source_file": file.filename or "",
            "records": result["records"],
            "months": result["months"],
            "items_found": result["items_found"],
            "warnings": result["warnings"] + sail_set_warnings(result["records"]),
            "record_count": len(result["records"]),
            "has_existing": bool(conflicts),
            "existing_conflicts_count": len(conflicts),
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
async def insert_mou_plan(payload: dict):
    """Body: { records: [{report_month, plant_name, item_name, value}, ...],
               source_file, confirm_replace: bool }"""
    records = payload.get("records", [])
    if not records:
        raise HTTPException(status_code=400, detail="No records to insert")
    conflicts = _existing_conflicts(records)
    if conflicts and not payload.get("confirm_replace"):
        months = sorted({c["report_month"] for c in conflicts})
        raise HTTPException(
            status_code=409,
            detail=(f"{len(conflicts)} MoU value(s) already exist for {months[0]} to {months[-1]}. "
                    "Confirm to overwrite them with the newly extracted figures."),
        )
    conn = db.connect()
    cur = conn.cursor()
    saved = 0
    try:
        for rec in records:
            cur.execute("""
                INSERT INTO mou_plan_table (report_month, plant_name, item_name, month_actual)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_month, plant_name, item_name)
                DO UPDATE SET month_actual = excluded.month_actual
            """, (rec["report_month"], rec["plant_name"], rec["item_name"], rec["value"]))
            saved += 1
        conn.commit()
    finally:
        conn.close()
    db.log_extraction(
        plant="SAIL", report_month=max(r["report_month"] for r in records),
        file_name=payload.get("source_file", ""), sheet_name="",
        source_type="MoU Plan", items_extracted=saved,
    )
    return {"status": "success", "saved": saved}
