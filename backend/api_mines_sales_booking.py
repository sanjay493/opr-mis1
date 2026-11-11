"""
Mines Sales Booking entry (/data-entry/mines?tab=mines-sales-booking): one FY
(Apr..Mar) of iron ore sales to 3rd party per mine x item --
the Plan (booking plan, also the Sales despatch plan), the booking Actual and
the Sales despatch Actual (both by Rail / Road). Tables: repo.mines
get_sales_booking_fy / save_sales_booking_fy.

  GET  /api/mines-sales-booking?fy_start=YYYY
  POST /api/mines-sales-booking   {kind, entries: [{report_month, mine_code, material_code, transport_mode?, qty}]}
"""
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from repo import mines as rmn

router = APIRouter(prefix="/api/mines-sales-booking", tags=["mines-sales-booking"])

MODES = ("RAIL", "ROAD")


def _fy_months(fy_start: int) -> list:
    return [f"{fy_start}-{m:02d}" for m in range(4, 13)] + [f"{fy_start + 1}-{m:02d}" for m in range(1, 4)]


@router.get("")
def get_sales_booking(fy_start: int = Query(...)):
    if not 2000 <= fy_start <= 2100:
        raise HTTPException(status_code=400, detail="fy_start out of range")
    months = _fy_months(fy_start)
    return {"fy_start": fy_start, "months": months, **rmn.get_sales_booking_fy(months)}


class SalesBookingEntry(BaseModel):
    report_month: str
    mine_code: str
    material_code: str
    transport_mode: Optional[str] = None
    qty: Optional[float] = None


class SalesBookingSaveRequest(BaseModel):
    kind: Literal["plan", "booking_actual", "despatch_actual"]
    entries: List[SalesBookingEntry] = []


@router.post("")
def save_sales_booking(request: SalesBookingSaveRequest):
    entries = [e.model_dump() for e in request.entries]
    if request.kind != "plan" and any(e["transport_mode"] not in MODES for e in entries):
        raise HTTPException(status_code=400, detail="transport_mode must be RAIL or ROAD")
    saved = rmn.save_sales_booking_fy(request.kind, entries)
    return {"status": "success", "saved": saved}
