"""BF Parameters report (bf_report.py) for /reports/excel.

  GET /api/bf-report/fys          -> {"fys": [2026, 2025, ...]}
  GET /api/bf-report?fy=2026      -> JSON report
  GET /api/bf-report/xlsx?fy=2026 -> .xlsx in the format sheet's layout
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


@router.get("/xlsx")
def report_xlsx(fy: int = Query(...)):
    _check(fy)
    rep = bf_report.build(fy)
    return Response(bf_report.build_xlsx(rep), media_type=_XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{bf_report.filename(rep, "xlsx")}"',
                             "Access-Control-Expose-Headers": "Content-Disposition"})
