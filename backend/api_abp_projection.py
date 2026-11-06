"""ABP production projection (abp_projection.py) for /reports/abp.

  GET /api/abp-projection/fys                     -> {"fys": [2026, 2025, ...]}
  GET /api/abp-projection?fy=2026                 -> JSON report
  GET /api/abp-projection/xlsx?fy=2026&decimals=1 -> .xlsx
  GET /api/abp-projection/pdf?fy=2026&decimals=1  -> .pdf (1 A4 landscape page)
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

import abp_projection as proj
from colors_loader import load_colors_config

# Plain `def` handlers: FastAPI runs them in its threadpool, so the DB reads
# and the synchronous Playwright render don't block the event loop.
router = APIRouter(prefix="/api/abp-projection", tags=["abp-projection"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _check(fy: int, decimals: int = 0):
    if not 1990 <= fy <= 2100:
        raise HTTPException(status_code=400, detail="fy must be the FY start year, e.g. 2026")
    if not 0 <= decimals <= 3:
        raise HTTPException(status_code=400, detail="decimals must be 0 to 3")


def _download(content, media_type, name):
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{name}"',
                             "Access-Control-Expose-Headers": "Content-Disposition"})


@router.get("/fys")
def fys():
    return {"fys": proj.available_fys()}


@router.get("")
def report(fy: int = Query(...)):
    _check(fy)
    return proj.build(fy)


@router.get("/xlsx")
def report_xlsx(fy: int = Query(...), decimals: int = Query(0)):
    _check(fy, decimals)
    rep = proj.build(fy)
    return _download(proj.build_xlsx(rep, load_colors_config(), decimals), _XLSX, proj.filename(rep, "xlsx"))


@router.get("/pdf")
def report_pdf(fy: int = Query(...), decimals: int = Query(0)):
    _check(fy, decimals)
    rep = proj.build(fy)
    pdf = proj.render_pdf(proj.build_html(rep, load_colors_config(), decimals))
    return _download(pdf, "application/pdf", proj.filename(rep, "pdf"))
