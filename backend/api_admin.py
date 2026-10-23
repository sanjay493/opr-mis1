"""
Administrator-only endpoints: manage the registration allow-list (add /
remove / bar emails), manage registered users (assign editor/admin role or
delete an account), view the activity log, and view the site-visit log.
"""
import json
from repo.conn import Row
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

import auth
import dbengine
from repo import ops as rop
from constants import PAGE_MODULES

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)])


class EmailOnly(BaseModel):
    email: EmailStr


class BarRequest(BaseModel):
    barred: bool


class RoleRequest(BaseModel):
    role: Optional[str] = None  # None | 'editor' | 'admin'


class PermissionsRequest(BaseModel):
    allowed_pages: Optional[List[str]] = None  # None = unrestricted (all pages)
    can_delete: bool = True


# ── allow-list management ────────────────────────────────────────────────────

@router.get("/allowed-emails")
def list_allowed_emails():
    conn = dbengine.connect()
    conn.row_factory = Row
    cur = conn.cursor()
    rows = [dict(r) for r in rop.allowed_email_rows(cur)]
    conn.close()
    return {"emails": rows}


@router.post("/allowed-emails")
def add_allowed_email(body: EmailOnly, admin: dict = Depends(auth.require_admin)):
    email = body.email.lower()
    now = datetime.now(timezone.utc).isoformat()
    conn = dbengine.connect()
    cur = conn.cursor()
    rop.upsert_allowed_email(cur, email, admin["email"], now)
    conn.commit()
    conn.close()
    auth.log_activity(admin, "insert", "allowed_emails", f"added/unbarred {email}")
    return {"status": "ok"}


@router.delete("/allowed-emails/{email}")
def remove_allowed_email(email: str, admin: dict = Depends(auth.require_admin)):
    email = email.lower()
    conn = dbengine.connect()
    cur = conn.cursor()
    rop.delete_allowed_email(cur, email)
    conn.commit()
    conn.close()
    auth.log_activity(admin, "delete", "allowed_emails", f"removed {email}")
    return {"status": "ok"}


@router.patch("/allowed-emails/{email}/bar")
def bar_allowed_email(email: str, body: BarRequest, admin: dict = Depends(auth.require_admin)):
    email = email.lower()
    now = datetime.now(timezone.utc).isoformat()
    conn = dbengine.connect()
    cur = conn.cursor()
    if not rop.allowed_email_exists_row(cur, email):
        conn.close()
        raise HTTPException(status_code=404, detail="Email is not on the allow-list.")
    rop.set_allowed_email_barred(cur, 1 if body.barred else 0, admin["email"] if body.barred else None,
                                 now if body.barred else None, email)
    conn.commit()
    conn.close()
    auth.log_activity(admin, "update", "allowed_emails", f"{'barred' if body.barred else 'unbarred'} {email}")
    return {"status": "ok"}


# ── user management ───────────────────────────────────────────────────────────

@router.get("/page-modules")
def list_page_modules():
    return {"modules": [{"key": k, "label": v["label"]} for k, v in PAGE_MODULES.items()]}


@router.get("/users")
def list_users():
    conn = dbengine.connect()
    conn.row_factory = Row
    cur = conn.cursor()
    rows = [dict(r) for r in rop.user_list_rows(cur)]
    for r in rows:
        r["allowed_pages"] = json.loads(r["allowed_pages"]) if r["allowed_pages"] else None
        r["can_delete"] = bool(r["can_delete"])
    conn.close()
    return {"users": rows}


@router.patch("/users/{user_id}/permissions")
def set_user_permissions(user_id: int, body: PermissionsRequest, admin: dict = Depends(auth.require_admin)):
    if body.allowed_pages is not None:
        unknown = set(body.allowed_pages) - set(PAGE_MODULES.keys())
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown page module(s): {', '.join(sorted(unknown))}")
    conn = dbengine.connect()
    cur = conn.cursor()
    row = rop.user_email_row(cur, user_id)
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    rop.set_user_permissions(
        cur,
        json.dumps(body.allowed_pages) if body.allowed_pages is not None else None,
        1 if body.can_delete else 0,
        datetime.now(timezone.utc).isoformat(),
        user_id,
    )
    conn.commit()
    conn.close()
    pages_desc = "all pages" if body.allowed_pages is None else f"{len(body.allowed_pages)} page(s)"
    auth.log_activity(
        admin, "update", "users",
        f"set permissions of {row[0]} to {pages_desc}, can_delete={body.can_delete}",
    )
    return {"status": "ok"}


@router.patch("/users/{user_id}/role")
def set_user_role(user_id: int, body: RoleRequest, admin: dict = Depends(auth.require_admin)):
    if body.role not in (None, "editor", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'editor', 'admin', or null.")
    conn = dbengine.connect()
    cur = conn.cursor()
    row = rop.user_email_row(cur, user_id)
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    rop.set_user_role(cur, body.role, datetime.now(timezone.utc).isoformat(), user_id)
    conn.commit()
    conn.close()
    auth.log_activity(admin, "update", "users", f"set role of {row[0]} to {body.role!r}")
    return {"status": "ok"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(auth.require_admin)):
    conn = dbengine.connect()
    cur = conn.cursor()
    row = rop.user_email_row(cur, user_id)
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    rop.delete_user(cur, user_id)
    conn.commit()
    conn.close()
    auth.log_activity(admin, "delete", "users", f"deleted account {row[0]}")
    return {"status": "ok"}


# ── activity log ──────────────────────────────────────────────────────────────

@router.get("/activity-log/filters")
def get_activity_log_filters():
    conn = dbengine.connect()
    cur = conn.cursor()
    users = [r[0] for r in rop.activity_log_user_rows(cur)]
    actions = [r[0] for r in rop.activity_log_action_rows(cur)]
    conn.close()
    return {"users": users, "actions": actions}


@router.get("/activity-log")
def get_activity_log(limit: int = 200, offset: int = 0, user_email: Optional[str] = None, action: Optional[str] = None):
    conn = dbengine.connect()
    conn.row_factory = Row
    cur = conn.cursor()
    where = []
    params = []
    if user_email:
        where.append("user_email=%s")
        params.append(user_email.lower())
    if action:
        where.append("action=%s")
        params.append(action)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = [dict(r) for r in rop.activity_log_rows(cur, clause, params, limit, offset)]
    conn.close()
    return {"entries": rows}


# ── notifications ────────────────────────────────────────────────────────────

@router.get("/notifications")
def get_admin_notifications(limit: int = 30):
    """Newest sign-ins and new anonymous visitors for the navbar bell
    (frontend/src/components/AdminNotifications.js). Unread state lives in
    the admin's browser as the last-seen id."""
    return {"notifications": rop.list_admin_notifications(max(1, min(limit, 100)))}


# ── site visits ──────────────────────────────────────────────────────────────

@router.get("/site-visits")
def get_site_visits(days: int = 30):
    """One row per distinct visitor (logged-in users grouped by email,
    anonymous ones by IP) in the last `days` days (days<=0 = all time),
    each with the list of pages they visited and how often. Grouped in
    Python — the row count in any
    reasonable window is small for an internal LAN tool."""
    conn = dbengine.connect()
    conn.row_factory = Row
    cur = conn.cursor()
    if days > 0:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = [dict(r) for r in rop.page_visit_rows_since(cur, since)]
    else:
        rows = [dict(r) for r in rop.page_visit_rows(cur)]
    conn.close()

    visitors: dict = {}
    for r in rows:
        key = r["user_email"] or f"anon:{r['ip_address'] or 'unknown'}"
        v = visitors.get(key)
        if v is None:
            v = visitors[key] = {
                "key": key,
                "user_email": r["user_email"],
                "user_name": r["user_name"],
                "ip_address": r["ip_address"],
                "is_logged_in": bool(r["user_email"]),
                "first_seen": r["timestamp"],
                "last_seen": r["timestamp"],
                "visit_count": 0,
                "_pages": {},
            }
        v["visit_count"] += 1
        v["last_seen"] = r["timestamp"]
        v["ip_address"] = r["ip_address"] or v["ip_address"]
        page = v["_pages"].get(r["path"])
        if page is None:
            page = v["_pages"][r["path"]] = {"path": r["path"], "count": 0, "last_seen": r["timestamp"]}
        page["count"] += 1
        page["last_seen"] = r["timestamp"]

    result = []
    for v in visitors.values():
        v["pages"] = sorted(v.pop("_pages").values(), key=lambda p: p["count"], reverse=True)
        result.append(v)
    result.sort(key=lambda v: v["last_seen"], reverse=True)
    return {"visitors": result}
