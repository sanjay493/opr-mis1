"""
API for the monthly rail loading entry (Data Entry > Reference & Records >
Monthly Rail Loading), which feeds MIS PDF page 40.05 — see rail_loading.py
for the item registry and the derived rows.

  GET  /api/rail-loading?month=YYYY-MM — the month's rows in print order:
       {kind, code, label, value, derived}; derived rows are worked out on
       save and are read-only in the form.
  POST /api/rail-loading — {report_month, values: {code: rakes | null}};
       replaces the month. Editors and admins only.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

import auth as _auth
import rail_loading
from api_unified_techno import _validate_month
from repo import rake as rrake

router = APIRouter(prefix="/api/rail-loading", tags=["rail-loading"])


def _rows(month: str) -> list:
    stored = {r["item_code"]: r["rakes"] for r in rrake.rail_loading_rows(month, month)}
    return [{"kind": kind, "code": code, "label": label, "value": stored.get(code),
             "derived": code in rail_loading.OTHERS}
            for kind, code, label in rail_loading.ITEMS if kind != "per_day"]


@router.get("")
def rail_loading_month(month: str = Query(..., description="YYYY-MM")):
    _validate_month(month)
    return {"report_month": month, "rows": _rows(month), "egom": rail_loading.EGOM,
            "egom_parts": list(rail_loading.EGOM_PARTS)}


@router.post("")
def rail_loading_save(payload: dict, user: dict = Depends(_auth.require_editor_or_admin)):
    month = payload.get("report_month") or ""
    _validate_month(month)
    values = {}
    for code, v in (payload.get("values") or {}).items():
        if code not in rail_loading.CODES:
            raise HTTPException(status_code=422, detail=f"Unknown item: {code}")
        if v is None or v == "":
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            raise HTTPException(status_code=422, detail=f"{rail_loading.LABELS[code]}: enter a number of rakes, 0 or more")
        values[code] = v
    try:
        values = {c: v for c, v in rail_loading.with_derived(values).items() if v is not None}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    saved = rail_loading.save_month(month, values, user.get("email"))
    return {"status": "ok", "saved": saved, "rows": _rows(month)}
