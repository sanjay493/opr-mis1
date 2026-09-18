"""
Blast Furnace Techno Report API — furnace-wise export for a custom month
range, a single month + its Apr->month cumulative, or a full financial year.
Backs /reports/techno-bf-furnace. See techno_bf_period.py for the data
layer this just validates input for and calls.

Endpoints:
  GET  /api/techno-bf-furnace/meta          – furnace roster + param registry
  POST /api/techno-bf-furnace/report        – JSON preview
  POST /api/techno-bf-furnace/excel         – .xlsx
  POST /api/techno-bf-furnace/pdf           – .pdf
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

import techno_bf_period as _bf
import page_bf_furnace_export as _export
from bf_benchmark_registry import SAIL_BF_UNITS_BY_PLANT

router = APIRouter(prefix="/api/techno-bf-furnace", tags=["techno-bf-furnace"])


class ReportRequest(BaseModel):
    furnaces: List[str]                  # "PLANT:UNIT" keys, e.g. "BSP:BF-8"
    params: Optional[List[str]] = None   # param keys; empty/None = all
    mode: str                            # "range" | "month_till" | "annual"
    start_month: Optional[str] = None    # mode == "range"
    end_month: Optional[str] = None      # mode == "range"
    month: Optional[str] = None          # mode == "month_till"
    fy_end_year: Optional[int] = None    # mode == "annual" (FY ending March of this year)


@router.get("/meta")
async def meta():
    return {
        "furnaces_by_plant": SAIL_BF_UNITS_BY_PLANT,
        "furnace_keys": [f["key"] for f in _bf.FURNACES],
        "params": _bf.REPORT_PARAMS,
    }


def _build(body: ReportRequest) -> dict:
    if not body.furnaces:
        raise HTTPException(400, "Select at least one furnace")
    try:
        furnaces = _bf.resolve_furnaces(body.furnaces)
        params = _bf.resolve_params(body.params)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if body.mode == "range":
        if not body.start_month or not body.end_month:
            raise HTTPException(400, "start_month and end_month are required for mode='range'")
        try:
            months = _bf.months_in_range(body.start_month, body.end_month)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return _bf.build_range_report(furnaces, params, months)

    if body.mode == "month_till":
        if not body.month:
            raise HTTPException(400, "month is required for mode='month_till'")
        m_label = _bf._month_label(body.month)
        ytd_months = None
        try:
            import db as _db
            ytd_months = _db.get_ytd_months(body.month)
        except Exception:
            pass
        cum_label = f"{_bf._month_label(ytd_months[0])} - {m_label} (Cumulative)" if ytd_months and len(ytd_months) > 1 else f"{m_label} (Cumulative)"
        periods = [
            {"label": f"{m_label} (Month)", "report_month": body.month, "period": "month"},
            {"label": cum_label, "report_month": body.month, "period": "till_month"},
        ]
        return _bf.build_direct_report(furnaces, params, periods)

    if body.mode == "annual":
        if not body.fy_end_year:
            raise HTTPException(400, "fy_end_year is required for mode='annual'")
        march = _bf.fy_march_month(body.fy_end_year)
        fy_label = f"{body.fy_end_year - 1}-{str(body.fy_end_year % 100).zfill(2)}"
        periods = [{"label": f"FY {fy_label} (Annual, Apr-Mar)", "report_month": march, "period": "till_month"}]
        return _bf.build_direct_report(furnaces, params, periods)

    raise HTTPException(400, f"Unknown mode: {body.mode}")


def _subtitle(body: ReportRequest) -> str:
    if body.mode == "range":
        return f"Period: {body.start_month} to {body.end_month}"
    if body.mode == "month_till":
        return f"Report month: {body.month}"
    if body.mode == "annual":
        return f"Financial Year ending March {body.fy_end_year}"
    return ""


@router.post("/report")
async def report(body: ReportRequest):
    return await run_in_threadpool(_build, body)


@router.post("/excel")
async def report_excel(body: ReportRequest):
    data = await run_in_threadpool(_build, body)
    content = await run_in_threadpool(_export.build_furnace_excel_bytes, data, _subtitle(body))
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="BF_Techno_Report.xlsx"'},
    )


@router.post("/pdf")
async def report_pdf(body: ReportRequest):
    data = await run_in_threadpool(_build, body)
    html = await run_in_threadpool(_export.build_furnace_pdf_html, data, _subtitle(body))
    content = await run_in_threadpool(_export.render_pdf_bytes, html)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="BF_Techno_Report.pdf"'},
    )
