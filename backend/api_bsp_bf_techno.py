"""
API endpoints for BSP Blast Furnace "V.PARAMETERS" techno data.

Stored under plant="BSP_BF" in techno_data — deliberately NOT plant="BSP",
which is already used by the existing "BSP 3-page-Tech" extractor
(techno_project/bsp_extractor.py) whose own unit set already includes
"BF-7"/"BF-8"/"BF_Shop" (see bsp_techno_map.json) with only a single BF
parameter each (bf_productivity). Sharing plant="BSP" here would silently
overwrite/be overwritten by that extractor's own BF rows on every save,
since techno_data is keyed on (plant, report_month, unit) with no room for
a second, richer source under the same three keys. Kept independent
instead, mirroring api_rsp_techno.py's structure.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

# Make techno_project importable when running from backend/
_TP_DIR = str(Path(__file__).parent / "techno_project")
if _TP_DIR not in sys.path:
    sys.path.insert(0, _TP_DIR)

from bsp_bf_technopara_extractor import BspBfTechnoExtractor  # noqa: E402
from db import init_db, upsert_techno_data, get_techno_data, get_techno_months  # noqa: E402

router = APIRouter(prefix="/api/bsp-bf-techno", tags=["bsp-bf-techno"])

PLANT = "BSP_BF"


def _validate_month(report_month: str):
    """Raise 400 if report_month is not in YYYY-MM format."""
    try:
        y, m = report_month.split('-')
        assert len(y) == 4 and 1 <= int(m) <= 12
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="report_month must be in YYYY-MM format, e.g. '2026-08'"
        )


@router.post("/preview")
async def preview_bsp_bf_techno(
    file: UploadFile = File(...),
    report_month: str = Form(..., description="Report month in YYYY-MM format, e.g. 2026-08"),
):
    """
    Extract the BSP BF_V.PARAMETERS workbook and return a preview — does
    NOT write to the database.

    Form fields:
      - file: .xls Blast Furnace "V.PARAMETERS" workbook (sheet 'FOR GM')
      - report_month: "2026-08"

    Returns: { report_month, units_extracted, total_params, records: [{unit, techno_json}] }
    """
    _validate_month(report_month)

    suffix = Path(file.filename or "upload.xls").suffix or ".xls"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        extractor = BspBfTechnoExtractor(tmp.name, report_month=report_month)
        records = extractor.extract()

        if not records:
            raise HTTPException(
                status_code=422,
                detail="No data extracted — verify this is the BF_V.PARAMETERS workbook "
                       "(sheet 'FOR GM') and that the selected month is actually reported in it.",
            )

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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@router.post("/insert")
async def insert_bsp_bf_techno(payload: dict):
    """
    Save previously previewed BSP BF techno records to the database.

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
                plant=PLANT,
                report_month=report_month,
                unit=rec["unit"],
                techno_json=rec["techno_json"],
                source_file=source_file,
            )
        return {
            "status": "ok",
            "message": f"Saved {len(records)} units for {report_month} to techno_data (plant={PLANT})",
            "report_month": report_month,
            "units_saved": len(records),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data")
async def get_data(
    report_month: str = Query(..., description="Report month: YYYY-MM"),
    unit: Optional[str] = Query(None, description="Optional unit name, e.g. 'BF-4'"),
):
    """Get BSP BF techno data for a specific month.

    Returns: { plant, report_month, unit_count, data: { unit: { month: {...}, till_month: {...} } } }
    """
    _validate_month(report_month)
    try:
        init_db()
        result = get_techno_data(PLANT, report_month, unit)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No BSP BF techno data found for month={report_month}"
                       + (f", unit={unit}" if unit else ""),
            )

        return {
            "plant": PLANT,
            "report_month": report_month,
            "unit_count": len(result),
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/months")
async def get_months():
    """Return list of available report months for BSP BF techno data, newest first."""
    try:
        init_db()
        months = get_techno_months(PLANT)
        return {"plant": PLANT, "months": months, "count": len(months)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
