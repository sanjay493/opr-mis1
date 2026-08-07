"""
Administrator-only endpoints: manage the registration allow-list (add /
remove / bar emails), manage registered users (assign editor/admin role or
delete an account), and view the activity log.
"""
import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

import auth
import db
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
    conn = db.connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM allowed_emails ORDER BY added_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"emails": rows}


@router.post("/allowed-emails")
def add_allowed_email(body: EmailOnly, admin: dict = Depends(auth.require_admin)):
    email = body.email.lower()
    now = datetime.now(timezone.utc).isoformat()
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO allowed_emails (email, added_by, added_at, barred)
           VALUES (?, ?, ?, 0)
           ON CONFLICT(email) DO UPDATE SET barred=0, added_by=excluded.added_by, added_at=excluded.added_at""",
        (email, admin["email"], now),
    )
    conn.commit()
    conn.close()
    auth.log_activity(admin, "insert", "allowed_emails", f"added/unbarred {email}")
    return {"status": "ok"}


@router.delete("/allowed-emails/{email}")
def remove_allowed_email(email: str, admin: dict = Depends(auth.require_admin)):
    email = email.lower()
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM allowed_emails WHERE email=?", (email,))
    conn.commit()
    conn.close()
    auth.log_activity(admin, "delete", "allowed_emails", f"removed {email}")
    return {"status": "ok"}


@router.patch("/allowed-emails/{email}/bar")
def bar_allowed_email(email: str, body: BarRequest, admin: dict = Depends(auth.require_admin)):
    email = email.lower()
    now = datetime.now(timezone.utc).isoformat()
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM allowed_emails WHERE email=?", (email,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Email is not on the allow-list.")
    cur.execute(
        "UPDATE allowed_emails SET barred=?, barred_by=?, barred_at=? WHERE email=?",
        (1 if body.barred else 0, admin["email"] if body.barred else None,
         now if body.barred else None, email),
    )
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
    conn = db.connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, name, role, profile_pic, allowed_pages, can_delete, created_at, updated_at "
        "FROM users ORDER BY created_at DESC"
    )
    rows = [dict(r) for r in cur.fetchall()]
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
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT email FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    cur.execute(
        "UPDATE users SET allowed_pages=?, can_delete=?, updated_at=? WHERE id=?",
        (
            json.dumps(body.allowed_pages) if body.allowed_pages is not None else None,
            1 if body.can_delete else 0,
            datetime.now(timezone.utc).isoformat(),
            user_id,
        ),
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
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT email FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    cur.execute(
        "UPDATE users SET role=?, updated_at=? WHERE id=?",
        (body.role, datetime.now(timezone.utc).isoformat(), user_id),
    )
    conn.commit()
    conn.close()
    auth.log_activity(admin, "update", "users", f"set role of {row[0]} to {body.role!r}")
    return {"status": "ok"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(auth.require_admin)):
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT email FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    cur.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    auth.log_activity(admin, "delete", "users", f"deleted account {row[0]}")
    return {"status": "ok"}


# ── activity log ──────────────────────────────────────────────────────────────

@router.get("/activity-log/filters")
def get_activity_log_filters():
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT user_email FROM activity_log WHERE user_email IS NOT NULL ORDER BY user_email")
    users = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT DISTINCT action FROM activity_log WHERE action IS NOT NULL ORDER BY action")
    actions = [r[0] for r in cur.fetchall()]
    conn.close()
    return {"users": users, "actions": actions}


@router.get("/activity-log")
def get_activity_log(limit: int = 200, offset: int = 0, user_email: Optional[str] = None, action: Optional[str] = None):
    conn = db.connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    where = []
    params = []
    if user_email:
        where.append("user_email=?")
        params.append(user_email.lower())
    if action:
        where.append("action=?")
        params.append(action)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    cur.execute(
        f"SELECT * FROM activity_log {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"entries": rows}
