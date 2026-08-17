"""
API endpoints for the "Power-OIS" monthly workbook — see
excel_extractors/excel_extractor_power_omi.py for the parsing itself and
its module docstring for the source workbook's layout.

Flow (mirrors /api/coal-omi's preview/insert/conflict pattern):
  1. POST /preview — extract (no DB writes), flag any existing
     power_data_table overlap for the records found.
  2. POST /insert — upsert the (client-confirmed) records into
     power_data_table. 409s on conflicts unless confirm_replace=true.
"""

import os
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File

sys.path.insert(0, str(Path(__file__).parent / "excel_extractors"))
from excel_extractor_power_omi import extract_power_omi  # noqa: E402

import db  # noqa: E402

router = APIRouter(prefix="/api/power-omi", tags=["power-omi"])


def _existing_conflicts(records: list) -> list:
    """Records whose (report_month, plant_name, item_name) already holds a
    non-null value in power_data_table."""
    conn = db.connect()
    cur = conn.cursor()
    conflicts = []
    try:
        for rec in records:
            cur.execute(
                "SELECT value FROM power_data_table "
                "WHERE report_month = ? AND plant_name = ? AND item_name = ?",
                (rec["report_month"], rec["plant_name"], rec["item_name"]),
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                conflicts.append(rec)
    finally:
        conn.close()
    return conflicts


@router.post("/preview")
async def preview_power_omi(file: UploadFile = File(..., description="Power-OIS report (.xlsx)")):
    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await file.read())
        tmp.close()

        try:
            result = extract_power_omi(tmp.name)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        conflicts = _existing_conflicts(result["records"])
        return {
            "status": "preview",
            "source_file": file.filename or "",
            "records": result["records"],
            "months": result["months"],
            "plants_found": result["plants_found"],
            "warnings": result["warnings"],
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
async def insert_power_omi(payload: dict):
    """Body: { records: [{report_month, plant_name, item_name, value}, ...],
               source_file, confirm_replace: bool }"""
    records = payload.get("records", [])
    source_file = payload.get("source_file", "")
    confirm_replace = bool(payload.get("confirm_replace"))

    if not records:
        raise HTTPException(status_code=400, detail="No records to insert")

    conflicts = _existing_conflicts(records)
    if conflicts and not confirm_replace:
        months = sorted({c["report_month"] for c in conflicts})
        plants = sorted({c["plant_name"] for c in conflicts})
        raise HTTPException(
            status_code=409,
            detail=(
                f"{len(conflicts)} value(s) already exist for "
                f"{', '.join(months)} ({', '.join(plants)}). "
                "Confirm to overwrite with the newly extracted figures."
            ),
        )

    conn = db.connect()
    cur = conn.cursor()
    saved = 0
    try:
        for rec in records:
            cur.execute("""
                INSERT INTO power_data_table (report_month, plant_name, item_name, value)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_month, plant_name, item_name)
                DO UPDATE SET value = excluded.value
            """, (rec["report_month"], rec["plant_name"], rec["item_name"], rec["value"]))
            saved += 1
        conn.commit()
    finally:
        conn.close()

    # report_month column is CHAR(7) — log against the latest month actually
    # present among the saved records (a single upload spans many months).
    latest_month = max((r["report_month"] for r in records), default="0000-00")
    db.log_extraction(
        plant="SAIL", report_month=latest_month,
        file_name=source_file, sheet_name="",
        source_type="Power-OIS Monthly Report",
        items_extracted=saved,
    )

    return {"status": "success", "saved": saved}
