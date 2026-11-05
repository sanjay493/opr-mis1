"""BF Parameters report (bf_report.py) for /reports/excel.

  GET /api/bf-report/fys          -> {"fys": [2026, 2025, ...]}
  GET /api/bf-report?fy=2026      -> JSON report
  GET /api/bf-report/xlsx?fy=2026 -> .xlsx in the format sheet's layout; optional
      comma lists hide_rows, hide_fys, hide_months, sections narrow it to the page
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

import bf_report

router = APIRouter(prefix="/api/bf-report", tags=["bf-report"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _check(fy: int):
    if not 1990 <= fy <= 2100:
        raise HTTPException(status_code=400, detail="fy must be the FY start year, e.g. 2026")


@router.get("/fys")
def fys():
    return {"fys": bf_report.available_fys()}


@router.get("")
def report(fy: int = Query(...)):
    _check(fy)
    return bf_report.build(fy)


def _list(text):
    return [v for v in text.split(",") if v]


@router.get("/xlsx")
def report_xlsx(fy: int = Query(...), hide_rows: str = "", hide_fys: str = "", hide_months: str = "",
                sections: str = ""):
    _check(fy)
    try:
        fys = [int(v) for v in _list(hide_fys)]
    except ValueError:
        raise HTTPException(status_code=400, detail="hide_fys must be FY start years, e.g. 2024,2025")
    rep = bf_report.narrow(bf_report.build(fy), _list(hide_rows), fys, _list(hide_months), _list(sections))
    return Response(bf_report.build_xlsx(rep), media_type=_XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{bf_report.filename(rep, "xlsx")}"',
                             "Access-Control-Expose-Headers": "Content-Disposition"})
