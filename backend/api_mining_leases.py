"""
API for the Details of SAIL Mining Leases entry (Data Entry > Reference >
Mining Leases), which feeds the PDF's Annexure-1 — see mining_leases.py for the
span rules.

  GET  /api/mining-leases — {rows}: every lease in print order, with the
       *_span columns (1 own row, N merged down over N rows, 0 covered).
  POST /api/mining-leases — {rows: [...]}; replaces the whole table. A span that
       does not fit is a 422 naming the row. Editors and admins only.
"""
from fastapi import APIRouter, Depends, HTTPException

import auth as _auth
import mining_leases

router = APIRouter(prefix="/api/mining-leases", tags=["mining-leases"])


@router.get("")
def mining_leases_list():
    return {"rows": mining_leases._stored()}


@router.post("")
def mining_leases_save(payload: dict, user: dict = Depends(_auth.require_editor_or_admin)):
    rows = payload.get("rows")
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise HTTPException(status_code=422, detail="rows must be a list of lease rows")
    try:
        saved = mining_leases.save(rows, user.get("email"))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"status": "ok", "saved": saved, "rows": mining_leases._stored()}
