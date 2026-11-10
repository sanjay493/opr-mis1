"""
Parliament annexures (/reports/parliament): the three sheets of
Report_format/work/HisParlia_Annexures.xlsx for the period Apr..<month>
of month's FY. See parl_annexures.py.

  GET /api/parl-annexures/{report}?month=YYYY-MM[&years=N]       -> JSON (with deviations)
  GET /api/parl-annexures/{report}/xlsx?month=YYYY-MM[&years=N]  -> .xlsx (sheet + "Data check")
  GET /api/parl-annexures/{report}/pdf?month=YYYY-MM[&years=N]   -> .pdf

report: production-performance | production-history | techno-history, or
"all" for the downloads (three sheets / pages; years = each report's default).
"""
import re

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

import parl_annexures as pa
import parl_annexures_export as px

router = APIRouter(prefix="/api/parl-annexures", tags=["parl-annexures"])

_SLUG = {s.replace("_", "-"): s for s in pa.BUILDERS}
_FILE = {
    "production_performance": "Annexure-II_Production_Performance",
    "production_history": "Production_History",
    "techno_history": "Annexure-III_Techno_History",
}
_MAX_YEARS = 25


def _check(report: str, month: str, years, allow_all=False):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month or ""):
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")
    if years is not None and not 1 <= years <= _MAX_YEARS:
        raise HTTPException(status_code=400, detail=f"years must be 1..{_MAX_YEARS}")
    if allow_all and report == "all":
        return list(pa.BUILDERS)
    if report not in _SLUG:
        raise HTTPException(status_code=404, detail=f"unknown report {report!r}")
    return [_SLUG[report]]


def _items(reports, month, years):
    return [(r, pa.build(r, month, years if len(reports) == 1 else None)) for r in reports]


def _fname(reports, month, ext):
    base = _FILE[reports[0]] if len(reports) == 1 else "Parliament_Annexures"
    return f"{base}_{month}.{ext}"


@router.get("/{report}")
def parl_annexure(report: str, month: str = Query(...), years: int | None = Query(None)):
    (r,) = _check(report, month, years)
    return pa.build(r, month, years)


@router.get("/{report}/xlsx")
def parl_annexure_xlsx(report: str, month: str = Query(...), years: int | None = Query(None)):
    reports = _check(report, month, years, allow_all=True)
    content = px.build_xlsx(_items(reports, month, years))
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{_fname(reports, month, "xlsx")}"'})


@router.get("/{report}/pdf")
def parl_annexure_pdf(report: str, month: str = Query(...), years: int | None = Query(None)):
    # A plain def: FastAPI runs it in its threadpool, so the DB reads and the
    # synchronous Playwright render do not block the event loop.
    reports = _check(report, month, years, allow_all=True)
    content = px.render_pdf(_items(reports, month, years))
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{_fname(reports, month, "pdf")}"'})
