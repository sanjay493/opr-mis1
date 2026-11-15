"""
API for the monthly rail loading entry (Data Entry > Reference & Records >
Monthly Rail Loading), which feeds MIS PDF page 40.05 — see rail_loading.py
for the item registry and the derived rows.

  GET  /api/rail-loading?month=YYYY-MM — the month's rows in print order:
       {kind, code, label, value, derived, from_file}; derived rows are worked
       out on save, from_file rows (OGOM / JGOM in a month the mines' rake
       record covers) show the record's count; both are read-only in the
       form. egom_file = the record's OGOM + JGOM, to set beside the typed EGOM.
  POST /api/rail-loading — {report_month, values: {code: rakes | null}};
       replaces the month. Editors and admins only.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

import auth as _auth
import rail_loading
from api_unified_techno import _validate_month
from repo import rake as rrake

router = APIRouter(prefix="/api/rail-loading", tags=["rail-loading"])


def _from_file(month: str) -> dict:
    """{"ore_ogom": n, "ore_jgom": n} when the mines' rake record covers the month, else {}."""
    return rail_loading.mines_overlay(month, month).get(month, {})


def _month(month: str) -> dict:
    stored = {r["item_code"]: r["rakes"] for r in rrake.rail_loading_rows(month, month)}
    file = _from_file(month)
    rows = [{"kind": kind, "code": code, "label": label, "value": file.get(code, stored.get(code)),
             "derived": code in rail_loading.OTHERS, "from_file": code in file}
            for kind, code, label in rail_loading.ITEMS if kind != "per_day"]
    return {"report_month": month, "rows": rows, "egom": rail_loading.EGOM,
            "egom_parts": list(rail_loading.EGOM_PARTS), "egom_file": sum(file.values()) if file else None}


@router.get("")
def rail_loading_month(month: str = Query(..., description="YYYY-MM")):
    _validate_month(month)
    return _month(month)


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
    for code in _from_file(month):           # the rake record's rows are never typed
        values.pop(code, None)
    try:
        values = {c: v for c, v in rail_loading.with_derived(values).items() if v is not None}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    saved = rail_loading.save_month(month, values, user.get("email"))
    return {"status": "ok", "saved": saved, **_month(month)}
