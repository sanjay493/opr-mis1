"""
Breakdown log API — plant/unit-wise unplanned-downtime events, entered ad hoc
(full CRUD), used alongside capital_repair_table by production_loss_analysis.py
to explain Hot Metal / Crude Steel / Finished Steel shortfalls vs ABP.

Endpoints:
  GET    /api/breakdown                – list, filtered by plant/fy/unit_type/unit_name
  GET    /api/breakdown/cr-candidates  – capital repairs an entry may really be (best first)
  POST   /api/breakdown                – create
  PATCH  /api/breakdown/{id}            – edit
  DELETE /api/breakdown/{id}            – delete

capital_repair_id: a capital repair the plant also logged here (exact
date-times + a remark naming it) is linked to its capital_repair_table row,
and every report then counts the event once, as the CR - see bd_cr_link.py.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

import bd_cr_link
import db as _db
from plant_registry import UNIT_TYPES, is_valid_unit

router = APIRouter(prefix="/api/breakdown", tags=["breakdown"])


def _is_shop(unit_name: Optional[str]) -> bool:
    return (unit_name or "").strip().lower() == "shop"


def _validate_unit(plant: str, unit_type: str, unit_name: str, sms_subtag: Optional[str]):
    if unit_type not in UNIT_TYPES:
        raise HTTPException(400, f"Unknown unit_type '{unit_type}'")
    # A whole-shop breakdown (unit_name == "Shop") is allowed for any unit
    # type and needs no Converter/Caster sub-tag — it's the entire shop down.
    if unit_type == "SMS" and not _is_shop(unit_name) and sms_subtag not in ("CONVERTER", "CASTER"):
        raise HTTPException(400, "sms_subtag ('CONVERTER' or 'CASTER') is required for a specific SMS unit")
    if not is_valid_unit(plant, unit_type, unit_name, include_shop=True):
        raise HTTPException(400, f"'{unit_name}' is not a known {unit_type} unit for {plant}")


def _validate_ts(start_ts: str, end_ts: Optional[str], is_ongoing: bool):
    if not start_ts or len(start_ts) < 10:
        raise HTTPException(400, "start_ts must be 'YYYY-MM-DD HH:MM' (or at least 'YYYY-MM-DD')")
    if not is_ongoing:
        if not end_ts:
            raise HTTPException(400, "end_ts is required unless is_ongoing is true")
        if end_ts < start_ts:
            raise HTTPException(400, "end_ts must not be before start_ts")


_CR_COLS = ("id", "plant", "fy", "shop", "equipment", "activity", "actual_start", "actual_end", "actual_ongoing")


def _actual_crs(plant: str) -> list:
    """The plant's capital repairs that have actual dates (linkable)."""
    conn = _db.connect()
    try:
        cur = conn.execute(
            f"SELECT {', '.join(_CR_COLS)} FROM capital_repair_table "
            "WHERE plant=? AND actual_start IS NOT NULL AND actual_start<>''", (plant,))
        return [dict(zip(_CR_COLS, r)) for r in cur.fetchall()]
    finally:
        conn.close()


def _validate_cr_link(plant: str, cr_id: Optional[int]):
    if cr_id is None:
        return
    conn = _db.connect()
    try:
        row = conn.execute("SELECT plant FROM capital_repair_table WHERE id=?", (cr_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(400, f"Capital repair {cr_id} not found")
    if row[0] != plant:
        raise HTTPException(400, f"Capital repair {cr_id} is {row[0]}'s, not {plant}'s")


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
    capital_repair_id: Optional[int] = None


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
    capital_repair_id: Optional[int] = None


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


@router.get("/cr-candidates")
async def cr_candidates(plant: str = Query(...), start_ts: str = Query(...),
                        end_ts: Optional[str] = Query(None), is_ongoing: bool = Query(False),
                        cause: str = Query(""), unit_name: str = Query("")):
    """The plant's capital repairs with actual dates starting within 60 days
    of start_ts, nearest first, with bd_cr_link's suggestion (if any) on top
    and its id in suggested_id."""
    crs = _actual_crs(plant)
    bd = {"plant": plant, "start_ts": start_ts, "end_ts": end_ts, "is_ongoing": is_ongoing,
          "cause": cause, "unit_name": unit_name}
    best = bd_cr_link.suggest_cr(bd, crs)
    try:
        s0 = date.fromisoformat(start_ts[:10])
    except ValueError:
        raise HTTPException(400, "start_ts must start with YYYY-MM-DD")

    def gap(cr):
        try:
            return abs((date.fromisoformat(str(cr["actual_start"])[:10]) - s0).days)
        except ValueError:
            return 10 ** 6
    near = sorted((c for c in crs if gap(c) <= 60), key=gap)
    if best is not None:
        near = [best] + [c for c in near if c["id"] != best["id"]]
    return {"suggested_id": best["id"] if best else None,
            "candidates": [{**c, "actual_ongoing": bool(c["actual_ongoing"])} for c in near]}


@router.post("")
async def create_breakdown(body: BreakdownCreate, request: Request):
    cause = (body.cause or "").strip()
    if not cause:
        raise HTTPException(400, "cause is required")
    sms_subtag = body.sms_subtag if (body.unit_type == "SMS" and not _is_shop(body.unit_name)) else None
    _validate_unit(body.plant, body.unit_type, body.unit_name, sms_subtag)
    _validate_ts(body.start_ts, body.end_ts, body.is_ongoing)
    _validate_cr_link(body.plant, body.capital_repair_id)

    new_id = _db.save_breakdown_entry(
        plant=body.plant, unit_type=body.unit_type, unit_name=body.unit_name, sms_subtag=sms_subtag,
        start_ts=body.start_ts, end_ts=None if body.is_ongoing else body.end_ts,
        is_ongoing=body.is_ongoing, cause=cause, hours_lost_override=body.hours_lost_override,
        created_by=_editor_email(request), capital_repair_id=body.capital_repair_id,
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
    sms_subtag = (fields.get("sms_subtag", row["sms_subtag"])
                  if (unit_type == "SMS" and not _is_shop(unit_name)) else None)
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
    if "capital_repair_id" in fields or "plant" in fields:
        _validate_cr_link(plant, fields.get("capital_repair_id", row.get("capital_repair_id")))

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
