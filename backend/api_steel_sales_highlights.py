"""
Steel Sales Performance — highlight bullets editor API.

Backs /data-entry/steel-sales-highlights: lets an editor/admin write the two
bullet lists (report-month, YTD) of the "Steel Sales Performance" report
page — see page_steel_sales_performance.py's module docstring for why. GET
is open (same as every other /entry-style lookup in this app —
RequireEditor only gates the edit FORM, not read access); POST requires an
editor/admin session, enforced server-side (not just the frontend's
RequireEditor gate).

Endpoints:
  GET  /api/steel-sales-highlights?report_month=YYYY-MM   – fetch saved bullets
  POST /api/steel-sales-highlights/save                     – upsert bullets
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

import auth
import db

router = APIRouter(prefix="/api/steel-sales-highlights", tags=["steel-sales-highlights"])


def _validate_month(report_month: str):
    try:
        y, m = report_month.split("-")
        assert len(y) == 4 and 1 <= int(m) <= 12
    except Exception:
        raise HTTPException(400, "report_month must be YYYY-MM, e.g. '2026-08'")


class SaveRequest(BaseModel):
    report_month: str
    month_items: List[str] = []
    ytd_items: List[str] = []


@router.get("")
async def get_highlights(report_month: str = Query(..., description="YYYY-MM")):
    _validate_month(report_month)
    saved = db.get_steel_sales_highlights(report_month)
    return {
        "report_month": report_month,
        "month_items": (saved or {}).get("month_items", []),
        "ytd_items": (saved or {}).get("ytd_items", []),
        "updated_by": (saved or {}).get("updated_by", ""),
        "updated_at": (saved or {}).get("updated_at", ""),
        "has_data": saved is not None,
    }


@router.post("/save")
async def save_highlights(body: SaveRequest, user: dict = Depends(auth.require_editor_or_admin)):
    _validate_month(body.report_month)

    # Drop fully-blank rows the editor added-then-left-empty (e.g. hit "+ Add
    # bullet" but never typed anything) rather than persisting clutter.
    month_items = [s.strip() for s in body.month_items if s.strip()]
    ytd_items = [s.strip() for s in body.ytd_items if s.strip()]

    db.save_steel_sales_highlights(
        body.report_month, month_items, ytd_items,
        updated_by=user.get("email", ""),
    )
    auth.log_activity(user, "update", "steel_sales_highlights", body.report_month)

    return {
        "status": "ok", "report_month": body.report_month,
        "month_items": len(month_items), "ytd_items": len(ytd_items),
    }
