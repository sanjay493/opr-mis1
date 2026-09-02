"""
Site-visit logging: a public, ungated endpoint the frontend beacons on every
page navigation (see frontend/src/components/VisitLogger.js). Identifies the
visitor from the same mis_session cookie auth.py already uses elsewhere
(anonymous if there isn't one), and the real client IP forwarded by
frontend/server.js as x-forwarded-for (the Next rewrite proxy itself doesn't
forward it). Feeds the admin-only summary at GET /api/admin/site-visits
(see api_admin.py).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

import auth
import db

router = APIRouter(prefix="/api", tags=["visits"])


class VisitLogBody(BaseModel):
    path: str


@router.post("/log-visit")
def log_visit(
    body: VisitLogBody,
    request: Request,
    user: Optional[dict] = Depends(auth.get_current_user_optional),
):
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")
    db.log_page_visit(ip, user, body.path[:255])
    return {"status": "ok"}
