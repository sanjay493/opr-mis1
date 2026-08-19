"""
Annual item-capacity API — rated annual capacity per plant/item, with a
mid-FY change history (commissioning/decommissioning), consumed by page4.py
to compute the "Capacity" column and CU% (Capacity Utilisation %) on the
Plant Wise Performance of Main Items page.

Endpoints:
  GET    /api/capacity            – list entries, filtered by plant/item
  POST   /api/capacity            – create one effective-dated entry
  PATCH  /api/capacity/{id}       – edit one entry
  DELETE /api/capacity/{id}       – delete one entry
"""

import sqlite3
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

import db as _db

router = APIRouter(prefix="/api/capacity", tags=["capacity"])

# The 4 Page-4 items capacity is tracked for (per user decision — Oven
# Pushing is a nos/day rate, Sinter/Pig Iron are intermediate items, not
# tracked here). Keep in sync with page4.py's PAGE4_ITEMS `has_capacity` flags.
CAPACITY_ITEMS = ["Hot Metal", "Total Crude Steel", "Saleable Steel", "Finished Steel"]

# Individual plants only — "5 Plants"/"SAIL" aggregate rows are always the
# sum of their member plants' own entries, never entered directly.
CAPACITY_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL"]


def _validate_month(effective_month: str):
    try:
        y, m = effective_month.split('-')
        assert len(y) == 4 and 1 <= int(m) <= 12
    except Exception:
        raise HTTPException(400, "effective_month must be YYYY-MM, e.g. '2026-04'")


def _validate_plant_item(plant: str, item: str):
    if plant not in CAPACITY_PLANTS:
        raise HTTPException(400, f"plant must be one of {CAPACITY_PLANTS}")
    if item not in CAPACITY_ITEMS:
        raise HTTPException(400, f"item must be one of {CAPACITY_ITEMS}")


class CapacityCreate(BaseModel):
    plant: str
    item: str
    effective_month: str          # 'YYYY-MM'
    annual_capacity: float        # '000 T / year
    reason: str = ""


class CapacityUpdate(BaseModel):
    plant: Optional[str] = None
    item: Optional[str] = None
    effective_month: Optional[str] = None
    annual_capacity: Optional[float] = None
    reason: Optional[str] = None


def _editor_email(request: Request) -> str:
    try:
        import auth as _auth
        token = request.cookies.get(_auth.COOKIE_NAME)
        payload = _auth.decode_session_token(token) if token else None
        if payload:
            user = _auth.get_user_by_id(int(payload["sub"]))
            if user:
                return user["email"]
    except Exception:
        pass
    return "unknown"


@router.get("")
async def list_capacity(plant: Optional[str] = Query(None), item: Optional[str] = Query(None)):
    rows = _db.list_capacity_entries(plant=plant, item=item)
    return {"rows": rows, "items": CAPACITY_ITEMS, "plants": CAPACITY_PLANTS}


@router.post("")
async def create_capacity(body: CapacityCreate, request: Request):
    _validate_plant_item(body.plant, body.item)
    _validate_month(body.effective_month)
    if body.annual_capacity <= 0:
        raise HTTPException(400, "annual_capacity must be greater than 0")
    try:
        new_id = _db.save_capacity_entry(
            plant=body.plant, item=body.item, effective_month=body.effective_month,
            annual_capacity=body.annual_capacity, reason=(body.reason or "").strip(),
            created_by=_editor_email(request),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            409,
            f"A capacity entry already exists for {body.plant}/{body.item} effective {body.effective_month} — edit it instead.",
        )
    return {"status": "ok", "id": new_id}


@router.patch("/{entry_id}")
async def update_capacity(entry_id: int, body: CapacityUpdate, request: Request):
    fields = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    if not fields:
        return {"status": "ok"}

    existing = _db.list_capacity_entries()
    row = next((r for r in existing if r["id"] == entry_id), None)
    if row is None:
        raise HTTPException(404, "Capacity entry not found")

    plant = fields.get("plant", row["plant_name"])
    item = fields.get("item", row["item_name"])
    if "plant" in fields or "item" in fields:
        _validate_plant_item(plant, item)
        fields["plant_name"] = fields.pop("plant")
        fields["item_name"] = fields.pop("item")

    if "effective_month" in fields:
        _validate_month(fields["effective_month"])

    if "annual_capacity" in fields and fields["annual_capacity"] <= 0:
        raise HTTPException(400, "annual_capacity must be greater than 0")

    if "reason" in fields:
        fields["reason"] = (fields["reason"] or "").strip()

    try:
        ok = _db.update_capacity_entry(entry_id, updated_by=_editor_email(request), **fields)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Another entry already exists for that plant/item/effective month.")
    if not ok:
        raise HTTPException(404, "Capacity entry not found")
    return {"status": "ok"}


@router.delete("/{entry_id}")
async def delete_capacity(entry_id: int):
    ok = _db.delete_capacity_entry(entry_id)
    if not ok:
        raise HTTPException(404, "Capacity entry not found")
    return {"status": "ok"}
