"""
Blast Furnace Techno Report API — furnace-wise export for a custom month
range (each month plus the range's cumulative) or one or more full financial
years.
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
    mode: str                            # "range" | "annual"
    start_month: Optional[str] = None    # mode == "range"
    end_month: Optional[str] = None      # mode == "range"
    fy_end_years: Optional[List[int]] = None  # mode == "annual" (FYs ending March of these years)
    fy_end_year: Optional[int] = None    # mode == "annual", single-FY form of fy_end_years


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

    if body.mode == "annual":
        years = _fy_end_years(body)
        if not years:
            raise HTTPException(400, "Select at least one financial year for mode='annual'")
        periods = [
            {"label": f"FY {y - 1}-{str(y % 100).zfill(2)} (Annual, Apr-Mar)",
             "report_month": _bf.fy_march_month(y), "period": "till_month"}
            for y in years
        ]
        return _bf.build_direct_report(furnaces, params, periods)

    raise HTTPException(400, f"Unknown mode: {body.mode}")


def _fy_end_years(body: ReportRequest) -> List[int]:
    years = body.fy_end_years or ([body.fy_end_year] if body.fy_end_year else [])
    return sorted(set(years))


def _subtitle(body: ReportRequest) -> str:
    if body.mode == "range":
        return f"Period: {body.start_month} to {body.end_month}"
    if body.mode == "annual":
        years = _fy_end_years(body)
        fys = ", ".join(f"{y - 1}-{str(y % 100).zfill(2)}" for y in years)
        return f"Financial Year{'s' if len(years) > 1 else ''}: {fys}"
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
