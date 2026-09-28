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
import secrets
import smtplib
import sqlite3
import ssl
import threading
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
OTP_MAX_ATTEMPTS = 5         # wrong guesses before a code is burned
OTP_RESEND_SECONDS = 60      # minimum gap between emailed codes per email+purpose
COOKIE_NAME = "mis_session"

# Two-step login: after the password check, a 6-digit code is emailed and must
# be entered before a session cookie is issued. Set LOGIN_2FA=off in
# backend/.env to fall back to password-only login (e.g. if outbound mail is
# down and nobody could otherwise sign in).
LOGIN_2FA_ENABLED = os.environ.get("LOGIN_2FA", "on").strip().lower() not in ("off", "0", "false", "no")

# The login challenge token is signed with a key derived from JWT_SECRET but
# distinct from it, so a challenge can never be replayed as a session cookie.
_CHALLENGE_SECRET = f"{JWT_SECRET}|login-challenge"


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


def create_login_challenge(user_id: int, email: str) -> str:
    """Short-lived token proving the password step passed; required, together
    with the emailed code, to finish a two-step login."""
    payload = {
        "sub": str(user_id),
        "email": email,
        "typ": "login_challenge",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, _CHALLENGE_SECRET, algorithm=JWT_ALGO)


def decode_login_challenge(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, _CHALLENGE_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        return None
    return payload if payload.get("typ") == "login_challenge" else None


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

# Wrong-guess counts per otp_codes.id. Kept in memory (the backend runs as a
# single process); a restart resets counts, which only ever lets a code get a
# few extra tries before it expires anyway.
_otp_failures: dict = {}
_otp_failures_lock = threading.Lock()


def _hash_code(code: str) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def generate_and_store_otp(email: str, purpose: str) -> str:
    """Creates a fresh 6-digit code, invalidates any earlier unused codes for
    the same email+purpose, stores the new one (hashed), and returns the
    plaintext code to be emailed."""
    code = f"{secrets.randbelow(1_000_000):06d}"
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


def otp_resend_wait_seconds(email: str, purpose: str) -> int:
    """Seconds until another code may be emailed for email+purpose (0 = now)."""
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        """SELECT created_at FROM otp_codes WHERE email=? AND purpose=?
           ORDER BY id DESC LIMIT 1""",
        (email, purpose),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return 0
    try:
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(row[0])).total_seconds()
    except (TypeError, ValueError):
        return 0
    return max(0, int(OTP_RESEND_SECONDS - elapsed))


def verify_otp(email: str, purpose: str, code: str) -> bool:
    """Checks the code against the latest unused, unexpired OTP for
    email+purpose. Marks it used on success so it can't be replayed, and
    after OTP_MAX_ATTEMPTS wrong guesses so a 6-digit code can't be
    brute-forced within its lifetime."""
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
    ok = bcrypt.checkpw((code or "").strip().encode("utf-8"), code_hash.encode("utf-8"))
    if ok:
        _otp_failures.pop(otp_id, None)
        cur.execute("UPDATE otp_codes SET used=1 WHERE id=?", (otp_id,))
        conn.commit()
    else:
        with _otp_failures_lock:
            _otp_failures[otp_id] = _otp_failures.get(otp_id, 0) + 1
            burned = _otp_failures[otp_id] >= OTP_MAX_ATTEMPTS
            if burned:
                _otp_failures.pop(otp_id, None)
        if burned:
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
    elif purpose == "login":
        subject = "SAIL MIS Portal — Your sign-in code"
        action = "finish signing in"
    else:
        subject = "SAIL MIS Portal — Your password reset passcode"
        action = "reset your password"
    body = (
        f"Your one-time passcode is: {code}\n\n"
        f"Enter this code to {action}. It expires in {OTP_EXPIRE_MINUTES} minutes.\n\n"
        + ("If you did not just try to sign in, someone may know your password — "
           "change it now from the portal's Forgot password page.\n"
           if purpose == "login" else
           "If you did not request this, you can ignore this email.")
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
