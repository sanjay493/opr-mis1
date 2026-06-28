"""
API endpoints for DSP Techno data extraction from PDF reports.
Saves to common techno_data table in JSON format.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

# Make techno_project importable
_TP_DIR = str(Path(__file__).parent / "techno_project")
if _TP_DIR not in sys.path:
    sys.path.insert(0, _TP_DIR)

from dsp_technopara_extractor import DspTechnoExtractor  # noqa: E402
from db import init_db, upsert_techno_data, get_techno_data, get_techno_months  # noqa: E402

router = APIRouter(prefix="/api/dsp-techno", tags=["dsp-techno"])


def _validate_month(report_month: str):
    """Validate month format YYYY-MM."""
    if not report_month:
        return  # Allow empty (auto-detect)
    try:
        y, m = report_month.split('-')
        assert len(y) == 4 and 1 <= int(m) <= 12
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="report_month must be in YYYY-MM format, e.g. '2026-03' or empty for auto-detect"
        )


@router.post("/extract")
async def extract_dsp_techno(
    file: UploadFile = File(..., description="DSP PDF report file"),
    report_month: str = Form("", description="Report month YYYY-MM (optional, auto-detected from PDF)"),
):
    """
    Extract techno data from DSP PDF report and save to techno_data table.

    Form fields:
      - file: .pdf DSP report
      - report_month: "2026-03" (optional, auto-detected from PDF)

    Returns: { status, plant, report_month, units_extracted, units }
    """
    _validate_month(report_month)

    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        # Extract data from PDF
        extractor = DspTechnoExtractor(tmp.name, report_month=report_month)
        records = extractor.extract()

        if not records:
            raise HTTPException(
                status_code=422,
                detail="No techno data extracted from DSP PDF. Verify file format and content."
            )

        # Save to database
        init_db()
        saved_count = 0

        for rec in records:
            try:
                upsert_techno_data(
                    plant=rec["plant"],
                    report_month=rec["report_month"],
                    unit=rec["unit"],
                    techno_json=rec["techno_json"],
                    source_file=file.filename or "",
                )
                saved_count += 1
            except Exception as e:
                print(f"Warning: Could not save {rec['unit']}: {e}")

        actual_month = records[0]["report_month"] if records else "unknown"

        return {
            "status": "ok",
            "plant": "DSP",
            "report_month": actual_month,
            "source_file": file.filename or "",
            "units_extracted": len(records),
            "units_saved": saved_count,
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


@router.post("/preview")
async def preview_dsp_techno(
    file: UploadFile = File(...),
    report_month: str = Form("", description="Report month YYYY-MM (optional)"),
):
    """
    Preview extracted DSP techno data without saving to database.

    Same as /extract but returns data for review without DB insert.
    """
    _validate_month(report_month)

    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        extractor = DspTechnoExtractor(tmp.name, report_month=report_month)
        records = extractor.extract()

        if not records:
            raise HTTPException(
                status_code=422,
                detail="No data extracted from DSP PDF."
            )

        preview_records = [
            {"unit": rec["unit"], "techno_json": rec["techno_json"]}
            for rec in records
        ]
        total_params = sum(
            len(r["techno_json"].get("month", {})) for r in preview_records
        )

        actual_month = records[0]["report_month"] if records else "unknown"

        return {
            "status": "preview",
            "plant": "DSP",
            "report_month": actual_month,
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


@router.get("/data")
async def get_data(
    report_month: str = Query(..., description="Report month: YYYY-MM"),
    unit: Optional[str] = Query(None, description="Optional: specific unit name"),
):
    """
    Retrieve DSP techno data from techno_data table.
    """
    try:
        y, m = report_month.split('-')
        assert len(y) == 4 and 1 <= int(m) <= 12
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="report_month must be in YYYY-MM format"
        )

    try:
        init_db()
        result = get_techno_data("DSP", report_month, unit)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No DSP techno data found for {report_month}"
            )

        return {
            "plant": "DSP",
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
    """
    List available report months for DSP.
    """
    try:
        init_db()
        months = get_techno_months("DSP")
        return {
            "plant": "DSP",
            "months": months,
            "count": len(months)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
