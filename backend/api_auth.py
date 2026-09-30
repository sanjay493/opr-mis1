"""
Authentication endpoints: registration (allow-listed emails only, OTP-verified),
login, logout, password reset/change (always OTP-verified — no "old password"
path), current-user info, and own-profile updates (name + picture).

Role assignment is NOT self-service: a freshly registered user has role=NULL
and can log in but cannot use any data-entry/upload/edit/delete page. Only an
administrator (see api_admin.py) can promote a user to 'editor' or 'admin'.
"""
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, UploadFile, File, Form
from pydantic import BaseModel, EmailStr

import auth
import db

router = APIRouter(prefix="/api/auth", tags=["auth"])

PROFILE_PICS_DIR = os.path.join(os.path.dirname(__file__), "static", "profile_pics")
os.makedirs(PROFILE_PICS_DIR, exist_ok=True)

_COOKIE_KW = auth.SESSION_COOKIE_KW


class EmailOnly(BaseModel):
    email: EmailStr


class RegisterVerify(BaseModel):
    email: EmailStr
    otp: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ResetVerify(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


def _public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name") or "",
        "role": user.get("role"),
        "profile_pic": user.get("profile_pic") or "",
    }


# ── registration ──────────────────────────────────────────────────────────────

@router.post("/register/request-otp")
def register_request_otp(body: EmailOnly):
    email = body.email.lower()
    if not auth.is_email_allowed(email):
        raise HTTPException(
            status_code=403,
            detail="This email isn't on the approved list for registration. Contact an administrator.",
        )
    if auth.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account already exists for this email — try logging in.")
    code = auth.generate_and_store_otp(email, "register")
    try:
        auth.send_otp_email(email, code, "register")
    except Exception:
        raise HTTPException(status_code=502, detail="Couldn't send the passcode email — the mail server is unreachable or misconfigured. Contact an administrator.")
    return {"status": "sent"}


@router.post("/register/verify")
def register_verify(body: RegisterVerify, response: Response):
    email = body.email.lower()
    if not auth.is_email_allowed(email):
        raise HTTPException(status_code=403, detail="This email isn't on the approved list for registration.")
    if auth.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account already exists for this email — try logging in.")
    if not auth.verify_otp(email, "register", body.otp):
        raise HTTPException(status_code=400, detail="That passcode is wrong or has expired.")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    now = datetime.now(timezone.utc).isoformat()
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO users (email, password_hash, name, role, profile_pic, created_at, updated_at)
           VALUES (?, ?, ?, NULL, '', ?, ?)""",
        (email, auth.hash_password(body.password), body.name.strip(), now, now),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()

    token = auth.create_session_token(user_id, email, None)
    response.set_cookie(auth.COOKIE_NAME, token, **_COOKIE_KW)
    return {"status": "ok", "user": _public_user({"id": user_id, "email": email, "name": body.name, "role": None})}


# ── login / logout ────────────────────────────────────────────────────────────

def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:2]}{'•' * max(1, len(local) - 2)}@{domain}"


def _send_login_code(email: str) -> None:
    code = auth.generate_and_store_otp(email, "login")
    try:
        auth.send_otp_email(email, code, "login")
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Couldn't send the sign-in code email — the mail server is unreachable or misconfigured. Contact an administrator.",
        )


def _start_session(user: dict, response: Response) -> dict:
    token = auth.create_session_token(user["id"], user["email"], user.get("role"))
    response.set_cookie(auth.COOKIE_NAME, token, **_COOKIE_KW)
    return {"status": "ok", "user": _public_user(user)}


@router.post("/login")
def login(body: LoginRequest, response: Response):
    """Step 1: password. With two-step login on, no session is issued here —
    a code is emailed and a short-lived challenge is returned for step 2."""
    user = auth.get_user_by_email(body.email.lower())
    if not user or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if auth._is_barred(user["email"]):
        raise HTTPException(status_code=403, detail="Your account has been barred by an administrator.")
    if not auth.LOGIN_2FA_ENABLED:
        return _start_session(user, response)

    # Reuse a code sent moments ago (e.g. double-submit) instead of spamming mail.
    if auth.otp_resend_wait_seconds(user["email"], "login") == 0:
        _send_login_code(user["email"])
    return {
        "status": "code_required",
        "challenge": auth.create_login_challenge(user["id"], user["email"]),
        "sent_to": _mask_email(user["email"]),
        "expires_in_minutes": auth.OTP_EXPIRE_MINUTES,
        "resend_after_seconds": auth.otp_resend_wait_seconds(user["email"], "login"),
    }


class LoginVerify(BaseModel):
    challenge: str
    code: str


class LoginResend(BaseModel):
    challenge: str


def _user_from_challenge(challenge: str) -> dict:
    payload = auth.decode_login_challenge(challenge)
    if not payload:
        raise HTTPException(status_code=401, detail="Your sign-in attempt expired — please enter your password again.")
    user = auth.get_user_by_id(int(payload["sub"]))
    if not user or user["email"] != payload.get("email"):
        raise HTTPException(status_code=401, detail="Your sign-in attempt expired — please enter your password again.")
    if auth._is_barred(user["email"]):
        raise HTTPException(status_code=403, detail="Your account has been barred by an administrator.")
    return user


@router.post("/login/verify")
def login_verify(body: LoginVerify, response: Response):
    """Step 2: the emailed code. Issues the session cookie on success."""
    user = _user_from_challenge(body.challenge)
    if not auth.verify_otp(user["email"], "login", body.code):
        raise HTTPException(
            status_code=400,
            detail=f"That code is wrong or has expired. After {auth.OTP_MAX_ATTEMPTS} wrong tries a code stops working — request a new one.",
        )
    return _start_session(user, response)


@router.post("/login/resend")
def login_resend(body: LoginResend):
    user = _user_from_challenge(body.challenge)
    wait = auth.otp_resend_wait_seconds(user["email"], "login")
    if wait > 0:
        raise HTTPException(status_code=429, detail=f"Please wait {wait} seconds before requesting another code.")
    _send_login_code(user["email"])
    return {
        "status": "sent",
        "sent_to": _mask_email(user["email"]),
        "resend_after_seconds": auth.otp_resend_wait_seconds(user["email"], "login"),
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"status": "ok"}


# ── password reset / change (always OTP-based) ───────────────────────────────

@router.post("/password/request-otp")
def password_request_otp(body: EmailOnly):
    email = body.email.lower()
    user = auth.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found for this email.")
    code = auth.generate_and_store_otp(email, "reset_password")
    try:
        auth.send_otp_email(email, code, "reset_password")
    except Exception:
        raise HTTPException(status_code=502, detail="Couldn't send the passcode email — the mail server is unreachable or misconfigured. Contact an administrator.")
    return {"status": "sent"}


@router.post("/password/verify")
def password_verify(body: ResetVerify):
    email = body.email.lower()
    user = auth.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found for this email.")
    if not auth.verify_otp(email, "reset_password", body.otp):
        raise HTTPException(status_code=400, detail="That passcode is wrong or has expired.")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET password_hash=?, updated_at=? WHERE email=?",
        (auth.hash_password(body.new_password), datetime.now(timezone.utc).isoformat(), email),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


# ── current user / profile ────────────────────────────────────────────────────

@router.get("/me")
def me(user: dict = Depends(auth.get_current_user)):
    return {"user": _public_user(user)}


@router.put("/profile")
def update_profile(
    name: Optional[str] = Form(default=None),
    picture: Optional[UploadFile] = File(default=None),
    user: dict = Depends(auth.get_current_user),
):
    conn = db.connect()
    cur = conn.cursor()
    updates = []
    params = []

    if name is not None:
        updates.append("name=?")
        params.append(name.strip())

    if picture is not None:
        ext = os.path.splitext(picture.filename or "")[1].lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            conn.close()
            raise HTTPException(status_code=400, detail="Unsupported image type.")
        fname = f"{user['id']}_{uuid.uuid4().hex[:8]}{ext}"
        with open(os.path.join(PROFILE_PICS_DIR, fname), "wb") as f:
            f.write(picture.file.read())
        updates.append("profile_pic=?")
        params.append(fname)

    if updates:
        updates.append("updated_at=?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(user["id"])
        cur.execute(f"UPDATE users SET {', '.join(updates)} WHERE id=?", params)
        conn.commit()

    cur.execute("SELECT * FROM users WHERE id=?", (user["id"],))
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    conn.close()
    return {"user": _public_user(dict(zip(cols, row)))}
