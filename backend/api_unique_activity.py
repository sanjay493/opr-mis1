"""
Unique Activities API

A record of one-off events worth keeping: a new unit started, a unit revived
after a prolonged capital repair, a first-ever product, ... Each activity is
a dated, titled paragraph, optionally tied to a plant / unit, with free tags
for searching.

Endpoints:
  GET    /api/unique-activities                – list (q, tag, plant, from, to filters)
  GET    /api/unique-activities/tags           – tags in use with counts + suggested tags
  POST   /api/unique-activities/add            – create (editor)
  POST   /api/unique-activities/{id}/update    – edit (editor)
  POST   /api/unique-activities/{id}/delete    – delete (editor with delete right)

Writes are gated by EditorAdminGateMiddleware via
constants.PAGE_MODULES["unique_activities"]; reads are open to every user.
"""

import re
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

import activity_context as _activity_context
from auth import get_current_user_optional
from repo import misc as rmisc

router = APIRouter(prefix="/api/unique-activities", tags=["unique-activities"])

PLANTS = ("SAIL", "BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL")
# Offered in the tag picker before anything has been used; any other tag may be typed.
SUGGESTED_TAGS = ("New unit start-up", "Revival after CR", "Commissioning", "First-ever", "Record",
                  "Milestone", "Blast Furnace", "SMS", "Rolling Mill", "Coke Oven", "Sinter Plant", "Mines")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_TAGS = 12


class ActivityRequest(BaseModel):
    activity_date: str                 # YYYY-MM-DD
    title: str
    description: str
    plant_code: Optional[str] = None
    unit_name: Optional[str] = None
    tags: List[str] = []


def _check_date(value: str, name: str) -> str:
    if not value or not _DATE_RE.match(value):
        raise HTTPException(400, f"{name} must be YYYY-MM-DD, e.g. '2026-10-15'")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, f"{name} '{value}' is not a real date")
    return value


def _clean_tags(tags: List[str]) -> List[str]:
    """Trim, collapse spaces and drop case-insensitive duplicates (the tag
    key is case-insensitive), keeping the first spelling and order."""
    out, seen = [], set()
    for t in tags:
        t = " ".join(str(t).split())
        if not t:
            continue
        if len(t) > 48:
            raise HTTPException(400, f"Tag '{t[:20]}…' is longer than 48 characters")
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    if len(out) > MAX_TAGS:
        raise HTTPException(400, f"At most {MAX_TAGS} tags per activity")
    return out


def _validated(body: ActivityRequest) -> dict:
    title = " ".join(body.title.split())
    description = body.description.strip()
    if not title:
        raise HTTPException(400, "Title is required")
    if len(title) > 200:
        raise HTTPException(400, "Title must be at most 200 characters")
    if not description:
        raise HTTPException(400, "Description is required")
    plant = (body.plant_code or "").strip().upper() or None
    if plant is not None and plant not in PLANTS:
        raise HTTPException(400, f"Unknown plant '{plant}'")
    unit = " ".join((body.unit_name or "").split()) or None
    if unit is not None and len(unit) > 64:
        raise HTTPException(400, "Unit must be at most 64 characters")
    return {
        "activity_date": _check_date(body.activity_date, "activity_date"),
        "plant_code": plant, "unit_name": unit, "title": title,
        "description": description, "tags": _clean_tags(body.tags),
    }


def _user_email(request: Request) -> str:
    try:
        from auth import COOKIE_NAME
        user = get_current_user_optional(request.cookies.get(COOKIE_NAME))
        return user["email"] if user else "unknown"
    except Exception:
        return "unknown"


@router.get("")
async def list_activities(
    q: Optional[str] = Query(None, description="text in title, description, unit or tags"),
    tag: Optional[str] = Query(None, description="one exact tag"),
    plant: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from", description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, alias="to", description="YYYY-MM-DD"),
):
    if from_date:
        _check_date(from_date, "from")
    if to_date:
        _check_date(to_date, "to")
    rows = rmisc.unique_activity_rows(q=(q or "").strip() or None, tag=(tag or "").strip() or None,
                                      plant_code=(plant or "").strip().upper() or None,
                                      date_from=from_date, date_to=to_date)
    return {"activities": rows, "count": len(rows)}


@router.get("/tags")
async def list_tags():
    used = [{"tag": t, "count": n} for t, n in rmisc.unique_activity_tag_counts()]
    return {"tags": used, "suggested": list(SUGGESTED_TAGS), "plants": list(PLANTS)}


@router.post("/add")
async def add_activity(body: ActivityRequest, request: Request):
    v = _validated(body)
    new_id = rmisc.save_unique_activity(None, v["activity_date"], v["plant_code"], v["unit_name"], v["title"],
                                        v["description"], v["tags"], _user_email(request))
    _activity_context.record(f"unique_activity/{new_id}", None, v)
    return {"status": "ok", "id": new_id}


@router.post("/{activity_id}/update")
async def update_activity(activity_id: int, body: ActivityRequest, request: Request):
    v = _validated(body)
    old = rmisc.unique_activity_row(activity_id)
    if old is None:
        raise HTTPException(404, f"No activity with id {activity_id}")
    rmisc.save_unique_activity(activity_id, v["activity_date"], v["plant_code"], v["unit_name"], v["title"],
                               v["description"], v["tags"], _user_email(request))
    _activity_context.record(f"unique_activity/{activity_id}", old, v)
    return {"status": "ok", "id": activity_id}


@router.post("/{activity_id}/delete")
async def delete_activity(activity_id: int):
    old = rmisc.unique_activity_row(activity_id)
    if old is None or not rmisc.delete_unique_activity(activity_id):
        raise HTTPException(404, f"No activity with id {activity_id}")
    _activity_context.record(f"unique_activity/{activity_id}", old, None)
    return {"status": "ok", "id": activity_id}
