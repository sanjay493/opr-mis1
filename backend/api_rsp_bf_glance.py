"""
API endpoints for the RSP Blast-Furnace "GLANCE" workbook (BF Department's
own monthly report, Report_format/Monthly/RSP/GLANCE -<Mon>'<YY>.xlsx).

A "final" source, same standing as /api/techno (the plant-wide Technopara
sheet) — records are MERGED into techno_data (non-null values win, existing
values from other sources are kept), never a blind overwrite. Preview
enriches with the current DB values so the frontend can show a DB-vs-
extracted comparison and let the user opt out of individual parameters
before saving (see PreviewReview / ExtractRow in
frontend/src/app/data-entry/techno/page.js).
"""

import os
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

_TP_DIR = str(Path(__file__).parent / "techno_project")
if _TP_DIR not in sys.path:
    sys.path.insert(0, _TP_DIR)

from rsp_bf_glance_extractor import RspBfGlanceExtractor  # noqa: E402
from db import init_db, merge_upsert_techno_data, enrich_techno_records_with_db  # noqa: E402
from api_unified_techno import validate_units_for_plant, _validate_month  # noqa: E402

router = APIRouter(prefix="/api/rsp-bf-glance", tags=["rsp-bf-glance"])


@router.post("/preview")
async def preview_rsp_bf_glance(
    file: UploadFile = File(..., description="RSP BF Department GLANCE workbook (.xlsx)"),
    report_month: str = Form(..., description="Report month in YYYY-MM format, e.g. 2026-07"),
):
    """Extract BF techno values from the GLANCE workbook without saving —
    returns records enriched with the current DB values for review."""
    _validate_month(report_month)

    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await file.read())
        tmp.close()

        extractor = RspBfGlanceExtractor(tmp.name, report_month=report_month)
        try:
            records = extractor.extract()
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
        enrich_techno_records_with_db(preview_records, "RSP", report_month)

        return {
            "status": "preview",
            "plant": "RSP",
            "report_month": report_month,
            "source_file": file.filename or "",
            "units_extracted": len(preview_records),
            "total_params": total_params,
            "records": preview_records,
            "warnings": extractor.warnings,
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
async def insert_rsp_bf_glance(payload: dict):
    """Merge previously-previewed GLANCE records into techno_data.

    Body: { report_month, source_file, records: [{unit, techno_json}] }
    """
    report_month = payload.get("report_month", "")
    source_file = payload.get("source_file", "")
    records = payload.get("records", [])

    _validate_month(report_month)
    if not records:
        raise HTTPException(status_code=400, detail="No records to insert")
    validate_units_for_plant("RSP", (rec.get("unit", "") for rec in records))

    init_db()
    saved_count = 0
    for rec in records:
        try:
            merge_upsert_techno_data(
                plant="RSP",
                report_month=report_month,
                unit=rec["unit"],
                new_techno_json=rec["techno_json"],
                source_file=source_file,
            )
            saved_count += 1
        except Exception as e:
            print(f"Warning: Could not save {rec.get('unit')}: {e}")

    return {
        "status": "ok",
        "plant": "RSP",
        "report_month": report_month,
        "source_file": source_file,
        "units_extracted": len(records),
        "units_saved": saved_count,
        "units": [rec["unit"] for rec in records],
    }
