"""
Breakdown log API — plant/unit-wise unplanned-downtime events, entered ad hoc
(full CRUD), used alongside capital_repair_table by production_loss_analysis.py
to explain Hot Metal / Crude Steel / Finished Steel shortfalls vs ABP.

Endpoints:
  GET    /api/breakdown                – list, filtered by plant/fy/unit_type/unit_name
  POST   /api/breakdown                – create
  PATCH  /api/breakdown/{id}            – edit
  DELETE /api/breakdown/{id}            – delete
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

import db as _db
from plant_registry import UNIT_TYPES, is_valid_unit

router = APIRouter(prefix="/api/breakdown", tags=["breakdown"])


def _validate_unit(plant: str, unit_type: str, unit_name: str, sms_subtag: Optional[str]):
    if unit_type not in UNIT_TYPES:
        raise HTTPException(400, f"Unknown unit_type '{unit_type}'")
    if unit_type == "SMS" and sms_subtag not in ("CONVERTER", "CASTER"):
        raise HTTPException(400, "sms_subtag ('CONVERTER' or 'CASTER') is required when unit_type is SMS")
    if not is_valid_unit(plant, unit_type, unit_name):
        raise HTTPException(400, f"'{unit_name}' is not a known {unit_type} unit for {plant}")


def _validate_ts(start_ts: str, end_ts: Optional[str], is_ongoing: bool):
    if not start_ts or len(start_ts) < 10:
        raise HTTPException(400, "start_ts must be 'YYYY-MM-DD HH:MM' (or at least 'YYYY-MM-DD')")
    if not is_ongoing:
        if not end_ts:
            raise HTTPException(400, "end_ts is required unless is_ongoing is true")
        if end_ts < start_ts:
            raise HTTPException(400, "end_ts must not be before start_ts")


class BreakdownCreate(BaseModel):
    plant: str
    unit_type: str
    unit_name: str
    sms_subtag: Optional[str] = None
    start_ts: str                       # 'YYYY-MM-DD HH:MM'
    end_ts: Optional[str] = None        # None when is_ongoing
    is_ongoing: bool = False
    cause: str
    hours_lost_override: Optional[float] = None


class BreakdownUpdate(BaseModel):
    plant: Optional[str] = None
    unit_type: Optional[str] = None
    unit_name: Optional[str] = None
    sms_subtag: Optional[str] = None
    start_ts: Optional[str] = None
    end_ts: Optional[str] = None
    is_ongoing: Optional[bool] = None
    cause: Optional[str] = None
    hours_lost_override: Optional[float] = None


def _editor_email(request: Request) -> str:
    """Best-effort attribution for created_by/updated_by — falls back to
    'unknown' rather than failing the request if the session lookup misses
    (this endpoint is already gated by EditorAdminGateMiddleware for writes,
    so a valid session cookie is present; this only recovers the email)."""
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
async def list_breakdowns(plant: Optional[str] = Query(None), fy: Optional[str] = Query(None),
                           unit_type: Optional[str] = Query(None), unit_name: Optional[str] = Query(None)):
    rows = _db.list_breakdown_entries(plant=plant, fy=fy, unit_type=unit_type, unit_name=unit_name)
    return {"rows": rows}


@router.post("")
async def create_breakdown(body: BreakdownCreate, request: Request):
    cause = (body.cause or "").strip()
    if not cause:
        raise HTTPException(400, "cause is required")
    sms_subtag = body.sms_subtag if body.unit_type == "SMS" else None
    _validate_unit(body.plant, body.unit_type, body.unit_name, sms_subtag)
    _validate_ts(body.start_ts, body.end_ts, body.is_ongoing)

    new_id = _db.save_breakdown_entry(
        plant=body.plant, unit_type=body.unit_type, unit_name=body.unit_name, sms_subtag=sms_subtag,
        start_ts=body.start_ts, end_ts=None if body.is_ongoing else body.end_ts,
        is_ongoing=body.is_ongoing, cause=cause, hours_lost_override=body.hours_lost_override,
        created_by=_editor_email(request),
    )
    return {"status": "ok", "id": new_id}


@router.patch("/{breakdown_id}")
async def update_breakdown(breakdown_id: int, body: BreakdownUpdate, request: Request):
    fields = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    if not fields:
        return {"status": "ok"}

    existing = _db.list_breakdown_entries()
    row = next((r for r in existing if r["id"] == breakdown_id), None)
    if row is None:
        raise HTTPException(404, "Breakdown event not found")

    plant = fields.get("plant", row["plant"])
    unit_type = fields.get("unit_type", row["unit_type"])
    unit_name = fields.get("unit_name", row["unit_name"])
    sms_subtag = fields.get("sms_subtag", row["sms_subtag"]) if unit_type == "SMS" else None
    if "unit_type" in fields or "unit_name" in fields or "sms_subtag" in fields or "plant" in fields:
        _validate_unit(plant, unit_type, unit_name, sms_subtag)
        fields["sms_subtag"] = sms_subtag

    start_ts = fields.get("start_ts", row["start_ts"])
    is_ongoing = fields.get("is_ongoing", bool(row["is_ongoing"]))
    end_ts = fields.get("end_ts", row["end_ts"])
    if is_ongoing:
        end_ts = None
        fields["end_ts"] = None
    if "start_ts" in fields or "end_ts" in fields or "is_ongoing" in fields:
        _validate_ts(start_ts, end_ts, is_ongoing)

    if "cause" in fields and not (fields["cause"] or "").strip():
        raise HTTPException(400, "cause cannot be blank")

    ok = _db.update_breakdown_entry(breakdown_id, updated_by=_editor_email(request), **fields)
    if not ok:
        raise HTTPException(404, "Breakdown event not found")
    return {"status": "ok"}


@router.delete("/{breakdown_id}")
async def delete_breakdown(breakdown_id: int):
    ok = _db.delete_breakdown_entry(breakdown_id)
    if not ok:
        raise HTTPException(404, "Breakdown event not found")
    return {"status": "ok"}
