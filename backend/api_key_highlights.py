"""
Key Highlights & Variances — narrative editor API.

Backs /data-entry/key-highlights: lets an editor/admin write the three
sections of the "Key Highlights & Variances" report page (Major
Achievements, Major Shortfalls / Areas of Concern, Focus Areas Going
Forward) that can't be computed from any DB table — see
page_key_highlights.py's module docstring for why. GET is open (same as
every other /entry-style lookup in this app — RequireEditor only gates the
edit FORM, not read access); POST requires an editor/admin session,
enforced server-side (not just the frontend's RequireEditor gate).

Endpoints:
  GET  /api/key-highlights?report_month=YYYY-MM   – fetch saved narrative
  POST /api/key-highlights/save                    – upsert narrative
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

import auth
import db

router = APIRouter(prefix="/api/key-highlights", tags=["key-highlights"])


def _validate_month(report_month: str):
    try:
        y, m = report_month.split("-")
        assert len(y) == 4 and 1 <= int(m) <= 12
    except Exception:
        raise HTTPException(400, "report_month must be YYYY-MM, e.g. '2026-07'")


class Achievement(BaseModel):
    text: str = ""
    subs: List[str] = []


class FocusArea(BaseModel):
    title: str = ""
    description: str = ""


class SaveRequest(BaseModel):
    report_month: str
    achievements: List[Achievement] = []
    shortfalls: List[str] = []
    focus_areas: List[FocusArea] = []


@router.get("")
async def get_narrative(report_month: str = Query(..., description="YYYY-MM")):
    _validate_month(report_month)
    saved = db.get_key_highlights_narrative(report_month)
    return {
        "report_month": report_month,
        "achievements": (saved or {}).get("achievements", []),
        "shortfalls": (saved or {}).get("shortfalls", []),
        "focus_areas": (saved or {}).get("focus_areas", []),
        "updated_by": (saved or {}).get("updated_by", ""),
        "updated_at": (saved or {}).get("updated_at", ""),
        "has_data": saved is not None,
    }


@router.post("/save")
async def save_narrative(body: SaveRequest, user: dict = Depends(auth.require_editor_or_admin)):
    _validate_month(body.report_month)

    # Drop fully-blank rows the editor added-then-left-empty (e.g. hit "+ Add
    # achievement" but never typed anything) rather than persisting clutter.
    achievements = [
        {"text": a.text.strip(), "subs": [s.strip() for s in a.subs if s.strip()]}
        for a in body.achievements if a.text.strip()
    ]
    shortfalls = [s.strip() for s in body.shortfalls if s.strip()]
    focus_areas = [
        {"title": f.title.strip(), "description": f.description.strip()}
        for f in body.focus_areas if f.title.strip() or f.description.strip()
    ]

    db.save_key_highlights_narrative(
        body.report_month, achievements, shortfalls, focus_areas,
        updated_by=user.get("email", ""),
    )
    auth.log_activity(user, "update", "key_highlights_narrative", body.report_month)

    return {
        "status": "ok", "report_month": body.report_month,
        "achievements": len(achievements), "shortfalls": len(shortfalls),
        "focus_areas": len(focus_areas),
    }
