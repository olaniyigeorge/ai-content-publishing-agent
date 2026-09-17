"""Allowlist check, OTP generation/hashing, rate limiting, session lifecycle.

§6 refinements from architecture.md, all implemented here:
1. request_code() never reveals whether the email is allowlisted — same
   response either way, real branching happens silently.
2. Rate limiting off login_attempts (no Redis).
3. OTP consumption via consumed_at, checked on verify.
"""

import random
import string
from datetime import UTC, datetime, timedelta

import bcrypt

from app.config import get_settings
from app.email import send_otp_email
from db.client import get_supabase
from shared.errors import NotAuthorized

RATE_LIMIT_WINDOW_MINUTES = 15
RATE_LIMIT_MAX_REQUESTS = 5


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _is_allowlisted(email: str) -> bool:
    db = get_supabase()
    domain = email.split("@")[-1]
    email_rows = (
        db.table("access_rules")
        .select("id")
        .eq("enabled", True)
        .eq("type", "email")
        .eq("value", email)
        .execute()
        .data
    )
    domain_rows = (
        db.table("access_rules")
        .select("id")
        .eq("enabled", True)
        .eq("type", "domain")
        .eq("value", domain)
        .execute()
        .data
    )
    rows = email_rows + domain_rows
    if not rows:
        return False
    # expires_at filtering done in-app since PostgREST `or_` above can't
    # cleanly combine with an `or(expires_at.is.null,expires_at.gt.now())` too.
    now = datetime.now(UTC)
    full_rows = (
        db.table("access_rules")
        .select("*")
        .in_("id", [r["id"] for r in rows])
        .execute()
        .data
    )
    return any(r["expires_at"] is None or datetime.fromisoformat(r["expires_at"]) > now for r in full_rows)


def _rate_limited(user_id: str) -> bool:
    db = get_supabase()
    since = (datetime.now(UTC) - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)).isoformat()
    rows = (
        db.table("login_attempts")
        .select("id")
        .eq("user_id", user_id)
        .gte("created_at", since)
        .execute()
        .data
    )
    return len(rows) >= RATE_LIMIT_MAX_REQUESTS


def _upsert_user(email: str) -> dict:
    db = get_supabase()
    existing = db.table("users").select("*").eq("email", email).execute().data
    if existing:
        return existing[0]
    return db.table("users").insert({"email": email}).execute().data[0]


def request_code(email: str) -> None:
    """Always returns None / does nothing observable to the caller — the
    endpoint returns the same generic message regardless of what happens
    here. Allowlist rejection and rate limiting are both silent."""
    email = _normalize_email(email)
    print(f"request_code: email {email}")
            
    if not _is_allowlisted(email):
        print(f"request_code: email {email} not allowlisted, silently ignoring")
        return  # silent — do not create a user or attempt row for a non-allowlisted email

    user = _upsert_user(email)
    if _rate_limited(user["id"]):
        return  # silent — logged server-side only, never surfaced

    settings = get_settings()
    code = "".join(random.choices(string.digits, k=6))
    code_hash = bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()
    expires_at = (datetime.now(UTC) + timedelta(minutes=settings.otp_ttl_minutes)).isoformat()

    db = get_supabase()
    db.table("login_attempts").insert(
        {
            "user_id": user["id"],
            "code_hash": code_hash,
            "expires_at": expires_at,
            "max_attempts": settings.otp_max_attempts,
        }
    ).execute()

    send_otp_email(email, code)


def verify_code(email: str, code: str) -> str:
    """Returns a session id (opaque token) on success. Raises NotAuthorized
    on any failure — wrong code, expired, already consumed, no attempt, or
    max sub-attempts exceeded — with the same generic message so this
    endpoint doesn't leak which failure mode occurred."""
    email = _normalize_email(email)
    db = get_supabase()
    user_rows = db.table("users").select("*").eq("email", email).execute().data
    if not user_rows:
        raise NotAuthorized("invalid or expired code")
    user = user_rows[0]

    now = datetime.now(UTC)
    attempts = (
        db.table("login_attempts")
        .select("*")
        .eq("user_id", user["id"])
        .is_("consumed_at", "null")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not attempts:
        raise NotAuthorized("invalid or expired code")
    attempt = attempts[0]

    if attempt["attempts"] >= attempt["max_attempts"]:
        raise NotAuthorized("invalid or expired code")
    if datetime.fromisoformat(attempt["expires_at"]) < now:
        raise NotAuthorized("invalid or expired code")

    db.table("login_attempts").update({"attempts": attempt["attempts"] + 1}).eq("id", attempt["id"]).execute()

    if not bcrypt.checkpw(code.encode(), attempt["code_hash"].encode()):
        raise NotAuthorized("invalid or expired code")

    db.table("login_attempts").update({"consumed_at": now.isoformat()}).eq("id", attempt["id"]).execute()
    db.table("users").update({"last_login_at": now.isoformat()}).eq("id", user["id"]).execute()

    settings = get_settings()
    session_expires = (now + timedelta(minutes=settings.session_ttl_minutes)).isoformat()
    session = db.table("sessions").insert({"user_id": user["id"], "expires_at": session_expires}).execute().data[0]
    return session["id"]


def get_user_for_session(session_id: str) -> dict | None:
    db = get_supabase()
    rows = db.table("sessions").select("*, users(*)").eq("id", session_id).execute().data
    if not rows:
        return None
    session = rows[0]
    if datetime.fromisoformat(session["expires_at"]) < datetime.now(UTC):
        return None
    return session["users"]


def logout(session_id: str) -> None:
    get_supabase().table("sessions").delete().eq("id", session_id).execute()
