"""SAIL Mill Production Performance (mills_performance.py) for /reports/excel.

  GET /api/mills-performance/fys          -> {"fys": [2026, 2025, ...]}
  GET /api/mills-performance?fy=2026      -> JSON report
  GET /api/mills-performance/xlsx?fy=2026 -> .xlsx
  GET /api/mills-performance/pdf?fy=2026  -> .pdf (1 A4 landscape page)
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

import app_actual_trend as trend
import mills_performance as mills
from colors_loader import load_colors_config

# Plain `def` handlers: FastAPI runs them in its threadpool, so the DB reads
# and the synchronous Playwright render don't block the event loop.
router = APIRouter(prefix="/api/mills-performance", tags=["mills-performance"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _check(fy: int):
    if not 1990 <= fy <= 2100:
        raise HTTPException(status_code=400, detail="fy must be the FY start year, e.g. 2026")


def _download(content, media_type, name):
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{name}"',
                             "Access-Control-Expose-Headers": "Content-Disposition"})


@router.get("/fys")
def fys():
    return {"fys": trend.available_fys()}


@router.get("")
def report(fy: int = Query(...)):
    _check(fy)
    return mills.build(fy)


@router.get("/xlsx")
def report_xlsx(fy: int = Query(...)):
    _check(fy)
    rep = mills.build(fy)
    return _download(mills.build_xlsx(rep, load_colors_config()), _XLSX, mills.filename(rep, "xlsx"))


@router.get("/pdf")
def report_pdf(fy: int = Query(...)):
    _check(fy)
    rep = mills.build(fy)
    pdf = mills.render_pdf(mills.build_html(rep, load_colors_config()))
    return _download(pdf, "application/pdf", mills.filename(rep, "pdf"))
