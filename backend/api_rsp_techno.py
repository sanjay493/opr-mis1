"""
API endpoints for RSP Technopara data.
Independent of the existing techno_actuals / techno_param tables.
"""

import os
import sys
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

# Make techno_project importable when running from backend/
_TP_DIR = str(Path(__file__).parent / "techno_project")
if _TP_DIR not in sys.path:
    sys.path.insert(0, _TP_DIR)

from extractor import TechnoExtractor  # noqa: E402  (path set above)
from db import DB_PATH, init_db, upsert_techno_data, get_techno_data, get_techno_months

router = APIRouter(prefix="/api/rsp-techno", tags=["rsp-techno"])


def _validate_month(report_month: str):
    """Raise 400 if report_month is not in YYYY-MM format."""
    try:
        y, m = report_month.split('-')
        assert len(y) == 4 and 1 <= int(m) <= 12
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="report_month must be in YYYY-MM format, e.g. '2026-05'"
        )


@router.post("/preview")
async def preview_rsp_techno(
    file: UploadFile = File(...),
    report_month: str = Form(..., description="Report month in YYYY-MM format, e.g. 2026-05"),
):
    """
    Extract RSP technopara Excel and return a preview — does NOT write to the database.

    Form fields:
      - file: .xlsx Excel file (RSP Technopara sheet named 'page1-8')
      - report_month: "2026-05"

    Returns: { report_month, units_extracted, records: [{unit, techno_json}] }
    """
    _validate_month(report_month)

    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        extractor = TechnoExtractor(tmp.name, report_month=report_month)
        records = extractor.extract()

        if not records:
            raise HTTPException(
                status_code=422,
                detail="No data extracted — verify the sheet is named 'page1-8' and contains month headers in row 3.",
            )

        # Return extracted records for frontend preview — no DB write here
        preview_records = [
            {"unit": rec["unit"], "techno_json": rec["techno_json"]}
            for rec in records
        ]
        total_params = sum(
            len(r["techno_json"].get("month", {})) for r in preview_records
        )
        return {
            "status": "preview",
            "report_month": report_month,
            "source_file": file.filename or "",
            "units_extracted": len(preview_records),
            "total_params": total_params,
            "records": preview_records,
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
async def insert_rsp_techno(payload: dict):
    """
    Save previously previewed RSP techno records to the database.

    Body: { report_month, source_file, records: [{unit, techno_json}] }

    Returns: { status, report_month, units_saved }
    """
    report_month = payload.get("report_month", "")
    source_file = payload.get("source_file", "")
    records = payload.get("records", [])

    _validate_month(report_month)
    if not records:
        raise HTTPException(status_code=400, detail="No records to insert")

    try:
        init_db()
        for rec in records:
            upsert_techno_data(
                plant="RSP",
                report_month=report_month,
                unit=rec["unit"],
                techno_json=rec["techno_json"],
                source_file=source_file,
            )
        return {
            "status": "ok",
            "message": f"Saved {len(records)} units for {report_month} to techno_data",
            "report_month": report_month,
            "units_saved": len(records),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract")
async def extract_rsp_techno(
    file: UploadFile = File(...),
    report_month: str = Form(..., description="Report month in YYYY-MM format, e.g. 2026-05"),
):
    """Extract and immediately save (no preview). Kept for programmatic/API use."""
    _validate_month(report_month)

    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        extractor = TechnoExtractor(tmp.name, report_month=report_month)
        records = extractor.extract()

        if not records:
            raise HTTPException(
                status_code=422,
                detail="No data extracted — verify the sheet is named 'page1-8' and contains month headers in row 3.",
            )

        init_db()
        for rec in records:
            upsert_techno_data(
                plant="RSP",
                report_month=rec['report_month'],
                unit=rec['unit'],
                techno_json=rec['techno_json'],
                source_file=file.filename or '',
            )

        return {
            "status": "ok",
            "report_month": report_month,
            "units_extracted": len(records),
            "units": [rec['unit'] for rec in records],
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


@router.get("/data")
async def get_data(
    report_month: str = Query(..., description="Report month: YYYY-MM"),
    plant: str = Query("RSP", description="Plant code: BSP, DSP, RSP, BSL, ISP"),
    unit: Optional[str] = Query(None, description="Optional unit name, e.g. 'BF-1'"),
):
    """
    Get techno data for a specific plant and month.

    Returns: { plant, report_month, unit_count, data: { unit: { month: {...}, till_month: {...} } } }
    """
    _validate_month(report_month)
    try:
        init_db()
        result = get_techno_data(plant, report_month, unit)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No techno data found for plant={plant}, month={report_month}"
                       + (f", unit={unit}" if unit else ""),
            )

        return {
            "plant": plant,
            "report_month": report_month,
            "unit_count": len(result),
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/months")
async def get_months(
    plant: str = Query(None, description="Optional plant filter: BSP, DSP, RSP, BSL, ISP"),
):
    """Return list of available report months in techno_data, newest first.
    Pass ?plant=RSP to filter by plant."""
    try:
        init_db()
        months = get_techno_months(plant)
        return {"plant": plant, "months": months, "count": len(months)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/units")
async def get_units(
    report_month: str = Query(..., description="Report month: YYYY-MM"),
    plant: str = Query("RSP", description="Plant code: BSP, DSP, RSP, BSL, ISP"),
):
    """Return list of unit names stored for a given plant and report month."""
    _validate_month(report_month)
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT unit FROM techno_data WHERE plant = ? AND report_month = ? ORDER BY unit",
            [plant, report_month],
        )
        units = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {"plant": plant, "report_month": report_month, "units": units, "count": len(units)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
