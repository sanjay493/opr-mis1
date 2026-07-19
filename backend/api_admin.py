"""
Administrator-only endpoints: manage the registration allow-list (add /
remove / bar emails), manage registered users (assign editor/admin role or
delete an account), and view the activity log.
"""
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

import auth
import db

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)])


class EmailOnly(BaseModel):
    email: EmailStr


class BarRequest(BaseModel):
    barred: bool


class RoleRequest(BaseModel):
    role: Optional[str] = None  # None | 'editor' | 'admin'


# ── allow-list management ────────────────────────────────────────────────────

@router.get("/allowed-emails")
def list_allowed_emails():
    conn = sqlite3.connect(db.DB_PATH)
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
    conn = sqlite3.connect(db.DB_PATH)
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
    conn = sqlite3.connect(db.DB_PATH)
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
    conn = sqlite3.connect(db.DB_PATH)
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

@router.get("/users")
def list_users():
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, email, name, role, profile_pic, created_at, updated_at FROM users ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"users": rows}


@router.patch("/users/{user_id}/role")
def set_user_role(user_id: int, body: RoleRequest, admin: dict = Depends(auth.require_admin)):
    if body.role not in (None, "editor", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'editor', 'admin', or null.")
    conn = sqlite3.connect(db.DB_PATH)
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
    conn = sqlite3.connect(db.DB_PATH)
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

@router.get("/activity-log")
def get_activity_log(limit: int = 200, offset: int = 0, user_email: Optional[str] = None, action: Optional[str] = None):
    conn = sqlite3.connect(db.DB_PATH)
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
