"""
Auth core — password hashing, JWT sessions, OTP passcodes, and outbound email.

Roles: a freshly-registered user has role=NULL (can log in, no data-entry
access). An administrator promotes a user to 'editor' or 'admin'. Only emails
present in `allowed_emails` (and not barred) may register at all.

Every registration and every password change (forgotten or voluntary) is
completed by emailing a one-time passcode — there is no "change password with
just your old password" path, per spec.
"""
import os
import random
import secrets
import smtplib
import sqlite3
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Cookie, Depends, HTTPException, status

import db

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "")
SMTP_APP_PASSWORD = os.environ.get("SMTP_APP_PASSWORD", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGO = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 1 week
OTP_EXPIRE_MINUTES = 10
COOKIE_NAME = "mis_session"


# ── password hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── JWT sessions ──────────────────────────────────────────────────────────────

def create_session_token(user_id: int, email: str, role: Optional[str]) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_session_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        return None


# ── DB user lookups ──────────────────────────────────────────────────────────

def get_user_by_email(email: str) -> Optional[dict]:
    conn = db.connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = db.connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def is_email_allowed(email: str) -> bool:
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT barred FROM allowed_emails WHERE email=?", (email,))
    row = cur.fetchone()
    conn.close()
    return row is not None and row[0] == 0


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def _is_barred(email: str) -> bool:
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT barred FROM allowed_emails WHERE email=?", (email,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0] == 1)


def get_current_user(mis_session: Optional[str] = Cookie(default=None)) -> dict:
    if not mis_session:
        raise HTTPException(status_code=401, detail="Not logged in.")
    payload = decode_session_token(mis_session)
    if not payload:
        raise HTTPException(status_code=401, detail="Session expired or invalid — please log in again.")
    user = get_user_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists.")
    if _is_barred(user["email"]):
        raise HTTPException(status_code=403, detail="Your account has been barred by an administrator.")
    return user


def get_current_user_optional(mis_session: Optional[str] = Cookie(default=None)) -> Optional[dict]:
    if not mis_session:
        return None
    payload = decode_session_token(mis_session)
    if not payload:
        return None
    return get_user_by_id(int(payload["sub"]))


def require_role(*roles: str):
    """FastAPI dependency factory: raises 403 unless current user's role is
    one of `roles`. Usage: Depends(require_role("editor", "admin"))."""
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to do this — editor or administrator access required.",
            )
        return user
    return _dep


require_editor_or_admin = require_role("editor", "admin")
require_admin = require_role("admin")


# ── OTP passcodes ─────────────────────────────────────────────────────────────

def _hash_code(code: str) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def generate_and_store_otp(email: str, purpose: str) -> str:
    """Creates a fresh 6-digit code, invalidates any earlier unused codes for
    the same email+purpose, stores the new one (hashed), and returns the
    plaintext code to be emailed."""
    code = f"{random.randint(0, 999999):06d}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=OTP_EXPIRE_MINUTES)

    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE otp_codes SET used=1 WHERE email=? AND purpose=? AND used=0",
        (email, purpose),
    )
    cur.execute(
        """INSERT INTO otp_codes (email, purpose, code_hash, expires_at, used, created_at)
           VALUES (?, ?, ?, ?, 0, ?)""",
        (email, purpose, _hash_code(code), expires_at.isoformat(), now.isoformat()),
    )
    conn.commit()
    conn.close()
    return code


def verify_otp(email: str, purpose: str, code: str) -> bool:
    """Checks the code against the latest unused, unexpired OTP for
    email+purpose. Marks it used on success so it can't be replayed."""
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, code_hash, expires_at FROM otp_codes
           WHERE email=? AND purpose=? AND used=0
           ORDER BY id DESC LIMIT 1""",
        (email, purpose),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return False
    otp_id, code_hash, expires_at = row
    try:
        expired = datetime.fromisoformat(expires_at) < datetime.now(timezone.utc)
    except ValueError:
        expired = True
    if expired:
        conn.close()
        return False
    ok = bcrypt.checkpw(code.encode("utf-8"), code_hash.encode("utf-8"))
    if ok:
        cur.execute("UPDATE otp_codes SET used=1 WHERE id=?", (otp_id,))
        conn.commit()
    conn.close()
    return ok


# ── email sending ─────────────────────────────────────────────────────────────

def send_email(to_email: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.send_message(msg)


def send_otp_email(to_email: str, code: str, purpose: str) -> None:
    if purpose == "register":
        subject = "SAIL MIS Portal — Your registration passcode"
        action = "complete your registration"
    else:
        subject = "SAIL MIS Portal — Your password reset passcode"
        action = "reset your password"
    body = (
        f"Your one-time passcode is: {code}\n\n"
        f"Enter this code to {action}. It expires in {OTP_EXPIRE_MINUTES} minutes.\n\n"
        f"If you did not request this, you can ignore this email."
    )
    send_email(to_email, subject, body)


# ── activity log ──────────────────────────────────────────────────────────────

def log_activity(user: Optional[dict], action: str, entity: str, details: str = "") -> None:
    """action: 'insert' | 'update' | 'delete'."""
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO activity_log (user_email, user_name, action, entity, details, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            user.get("email") if user else None,
            user.get("name") if user else None,
            action,
            entity,
            details,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
