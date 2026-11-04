"""APP / MoU vs Actual performance trend (app_actual_trend.py) for
/reports/excel.

  GET /api/app-actual-trend/fys                         -> {"fys": [2026, 2025, ...]}
  GET /api/app-actual-trend?fy=2026&basis=app|mou       -> JSON report
  GET /api/app-actual-trend/xlsx?fy=2026&basis=app|mou  -> .xlsx
  GET /api/app-actual-trend/pdf?fy=2026&basis=app|mou   -> .pdf (3 A4 pages)
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

import app_actual_trend as trend
from colors_loader import load_colors_config

# Plain `def` handlers: FastAPI runs them in its threadpool, so the DB reads
# and the synchronous Playwright render don't block the event loop.
router = APIRouter(prefix="/api/app-actual-trend", tags=["app-actual-trend"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _check(fy: int, basis: str):
    if not 1990 <= fy <= 2100:
        raise HTTPException(status_code=400, detail="fy must be the FY start year, e.g. 2026")
    if basis not in trend.BASIS:
        raise HTTPException(status_code=400, detail="basis must be 'app' or 'mou'")


def _download(content, media_type, name):
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{name}"',
                             "Access-Control-Expose-Headers": "Content-Disposition"})


@router.get("/fys")
def fys():
    return {"fys": trend.available_fys()}


@router.get("")
def report(fy: int = Query(...), basis: str = Query("app")):
    _check(fy, basis)
    return trend.build(fy, basis)


@router.get("/xlsx")
def report_xlsx(fy: int = Query(...), basis: str = Query("app")):
    _check(fy, basis)
    rep = trend.build(fy, basis)
    return _download(trend.build_xlsx(rep, load_colors_config()), _XLSX, trend.filename(rep, "xlsx"))


@router.get("/pdf")
def report_pdf(fy: int = Query(...), basis: str = Query("app")):
    _check(fy, basis)
    rep = trend.build(fy, basis)
    pdf = trend.render_pdf(trend.build_html(rep, load_colors_config()))
    return _download(pdf, "application/pdf", trend.filename(rep, "pdf"))
