"""
API endpoints for BSP Techno data (BSP-3-page-Tech.xlsx and OISCO Excel).

Both file types extract data into the same techno_data table with plant='BSP'.
Multiple files can be uploaded for the same month — parameters are merged
(merge_upsert_techno_data) so one file doesn't wipe the other's data.

Endpoints (prefix /api/bsp-techno):
  POST /preview/techno   — preview from BSP-3-page-Tech.xlsx (no DB write)
  POST /preview/oisco    — preview from OISCO Excel (no DB write)
  POST /insert           — save previewed records to DB
  POST /extract/techno   — extract + save in one step (BSP-3-page-Tech.xlsx)
  POST /extract/oisco    — extract + save in one step (OISCO Excel)
  POST /inspect          — inspect file structure (sheet names, header rows)
"""

import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from openpyxl import load_workbook

_TP_DIR = str(Path(__file__).parent / "techno_project")
if _TP_DIR not in sys.path:
    sys.path.insert(0, _TP_DIR)

from bsp_extractor import BspTechnoExtractor            # noqa: E402
from bsp_oisco_extractor import BspOiscoExtractor       # noqa: E402
from db import init_db, merge_upsert_techno_data        # noqa: E402

router = APIRouter(prefix="/api/bsp-techno", tags=["bsp-techno"])


def _validate_month(report_month: str):
    try:
        y, m = report_month.split("-")
        assert len(y) == 4 and 1 <= int(m) <= 12
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="report_month must be in YYYY-MM format, e.g. '2026-05'",
        )


def _save_temp(file: UploadFile, content: bytes) -> Path:
    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


def _preview_response(records, report_month, source_file, source_type):
    total_params = sum(len(r["techno_json"].get("month", {})) for r in records)
    return {
        "status":          "preview",
        "source_type":     source_type,
        "report_month":    report_month,
        "source_file":     source_file,
        "units_extracted": len(records),
        "total_params":    total_params,
        "records": [{"unit": r["unit"], "techno_json": r["techno_json"]} for r in records],
    }


def _unlink(p: Path):
    try:
        p.unlink()
    except OSError:
        pass


# ── Preview ───────────────────────────────────────────────────────────────────

@router.post("/preview/techno")
async def preview_bsp_techno(
    file: UploadFile = File(...),
    report_month: str = Form(...),
):
    """Preview BSP-3-page-Tech.xlsx — does NOT write to DB."""
    _validate_month(report_month)
    tmp = _save_temp(file, await file.read())
    try:
        records = BspTechnoExtractor(str(tmp), report_month=report_month).extract()
        if not records:
            raise HTTPException(status_code=422,
                detail="No data extracted. Use /inspect to check the file structure, "
                       "then verify row numbers in bsp_techno_map.json.")
        return _preview_response(records, report_month, file.filename or "", "BSP-3-page-Tech.xlsx")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _unlink(tmp)


@router.post("/preview/oisco")
async def preview_bsp_oisco(
    file: UploadFile = File(...),
    report_month: str = Form(...),
):
    """Preview BSP OISCO Excel — does NOT write to DB."""
    _validate_month(report_month)
    tmp = _save_temp(file, await file.read())
    try:
        records = BspOiscoExtractor(str(tmp), report_month=report_month).extract()
        if not records:
            raise HTTPException(status_code=422,
                detail="No data extracted. Use /inspect to check the file structure, "
                       "then verify row numbers in bsp_oisco_map.json.")
        return _preview_response(records, report_month, file.filename or "", "BSP-OISCO-Techno.xlsx")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _unlink(tmp)


# ── Insert (after preview confirm) ───────────────────────────────────────────

@router.post("/insert")
async def insert_bsp_techno(payload: dict):
    """Save previewed BSP records to DB via merge-upsert.
    Body: { report_month, source_file, records: [{unit, techno_json}] }
    """
    report_month = payload.get("report_month", "")
    source_file  = payload.get("source_file",  "")
    records      = payload.get("records",       [])
    _validate_month(report_month)
    if not records:
        raise HTTPException(status_code=400, detail="No records to insert")
    try:
        init_db()
        for rec in records:
            merge_upsert_techno_data(
                plant="BSP", report_month=report_month,
                unit=rec["unit"], new_techno_json=rec["techno_json"],
                source_file=source_file,
            )
        return {"status": "ok", "report_month": report_month, "units_saved": len(records)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Extract-and-save (one step) ───────────────────────────────────────────────

@router.post("/extract/techno")
async def extract_bsp_techno(
    file: UploadFile = File(...),
    report_month: str = Form(...),
):
    """Extract BSP-3-page-Tech.xlsx and immediately save (merge-upsert)."""
    _validate_month(report_month)
    tmp = _save_temp(file, await file.read())
    try:
        records = BspTechnoExtractor(str(tmp), report_month=report_month).extract()
        if not records:
            raise HTTPException(status_code=422,
                detail="No data extracted. Use POST /api/bsp-techno/inspect to check "
                       "sheet names and header rows, then fix bsp_techno_map.json.")
        init_db()
        for rec in records:
            merge_upsert_techno_data(
                plant="BSP", report_month=rec["report_month"],
                unit=rec["unit"], new_techno_json=rec["techno_json"],
                source_file=file.filename or "",
            )
        return {
            "status": "ok", "source_type": "BSP-3-page-Tech.xlsx",
            "report_month": report_month,
            "units_extracted": len(records),
            "units": [r["unit"] for r in records],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _unlink(tmp)


@router.post("/extract/oisco")
async def extract_bsp_oisco(
    file: UploadFile = File(...),
    report_month: str = Form(...),
):
    """Extract BSP OISCO Excel and immediately save (merge-upsert)."""
    _validate_month(report_month)
    tmp = _save_temp(file, await file.read())
    try:
        records = BspOiscoExtractor(str(tmp), report_month=report_month).extract()
        if not records:
            raise HTTPException(status_code=422,
                detail="No data extracted. Use POST /api/bsp-techno/inspect to check "
                       "sheet names and header rows, then fix bsp_oisco_map.json.")
        init_db()
        for rec in records:
            merge_upsert_techno_data(
                plant="BSP", report_month=rec["report_month"],
                unit=rec["unit"], new_techno_json=rec["techno_json"],
                source_file=file.filename or "",
            )
        return {
            "status": "ok", "source_type": "BSP-OISCO-Techno.xlsx",
            "report_month": report_month,
            "units_extracted": len(records),
            "units": [r["unit"] for r in records],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _unlink(tmp)


# ── Diagnostic ────────────────────────────────────────────────────────────────

@router.post("/inspect")
async def inspect_bsp_file(file: UploadFile = File(...)):
    """
    Upload any BSP Excel file and get back its structure:
    sheet names, rows 1-11 of the active sheet (all non-empty cells per row).
    Use this to confirm sheet name, header row layout, and first data row
    before fixing row numbers in bsp_techno_map.json or bsp_oisco_map.json.
    """
    tmp = _save_temp(file, await file.read())
    try:
        wb = load_workbook(str(tmp), data_only=True)
        sheets_out = {}
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows_preview = {}
            for r in range(1, 12):
                row_vals = []
                for c in range(1, 25):
                    v = ws.cell(r, c).value
                    if v is not None:
                        row_vals.append({"col": c, "val": str(v)[:80]})
                if row_vals:
                    rows_preview[f"row_{r}"] = row_vals
            sheets_out[sheet_name] = rows_preview
        return {"filename": file.filename, "sheet_names": wb.sheetnames, "sheets": sheets_out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _unlink(tmp)
