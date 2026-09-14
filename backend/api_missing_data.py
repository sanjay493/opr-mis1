"""
API for the Missing Data Checklist (frontend: /todo/missing-data) — see
page_missing_data.py for the actual per-source presence logic and its
docstring for exactly what is/isn't covered.

Read-only: no gating beyond being logged in (matches other read-only
report-style GETs, e.g. api_breakdown.py's GET routes) - this is a
diagnostic view, not a data-entry endpoint.
"""
from fastapi import APIRouter, Query

from page_missing_data import generate_missing_data
from api_unified_techno import _validate_month

router = APIRouter(prefix="/api/missing-data", tags=["missing-data"])


@router.get("")
async def get_missing_data(month: str = Query(..., description="YYYY-MM")):
    _validate_month(month)
    return generate_missing_data(month)
