"""Auth flow — allowlist non-enumerable (§6 refinement 1), OTP consumption
(§6 refinement 3), rate limiting (§6 refinement 2). EDGE_CASES.md's auth
tier-3 entries."""

from datetime import UTC

import bcrypt
import pytest

from auth import service as auth_service
from shared.errors import NotAuthorized


def test_request_code_is_silent_for_allowlisted_and_non_allowlisted_alike(fake_db, monkeypatch):
    """The endpoint-level guarantee: request_code() itself never raises or
    returns anything that would let a caller distinguish the two cases."""
    monkeypatch.setattr(auth_service, "_is_allowlisted", lambda email: True)
    auth_service.request_code("allowed@koyatalent.com")  # returns None, no exception

    monkeypatch.setattr(auth_service, "_is_allowlisted", lambda email: False)
    auth_service.request_code("not-allowed@evil.com")  # returns None, no exception

    users = fake_db.table("users").select("*").execute().data
    assert len(users) == 1  # only the allowlisted email got a user row created
    assert users[0]["email"] == "allowed@koyatalent.com"


def test_verify_code_rejects_wrong_code(fake_db, monkeypatch):
    from datetime import datetime, timedelta

    user = fake_db.table("users").insert({"email": "a@koyatalent.com"}).execute().data[0]
    code_hash = bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode()
    fake_db.table("login_attempts").insert(
        {
            "user_id": user["id"],
            "code_hash": code_hash,
            "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
            "max_attempts": 5,
            "attempts": 0,
        }
    ).execute()

    with pytest.raises(NotAuthorized):
        auth_service.verify_code("a@koyatalent.com", "000000")


def test_verify_code_succeeds_once_then_consumed_code_cannot_be_reused(fake_db):
    from datetime import datetime, timedelta

    user = fake_db.table("users").insert({"email": "a@koyatalent.com"}).execute().data[0]
    code_hash = bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode()
    fake_db.table("login_attempts").insert(
        {
            "user_id": user["id"],
            "code_hash": code_hash,
            "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
            "max_attempts": 5,
            "attempts": 0,
        }
    ).execute()

    session_id = auth_service.verify_code("a@koyatalent.com", "123456")
    assert session_id

    with pytest.raises(NotAuthorized):
        auth_service.verify_code("a@koyatalent.com", "123456")


def test_expired_code_is_rejected(fake_db):
    from datetime import datetime, timedelta

    user = fake_db.table("users").insert({"email": "a@koyatalent.com"}).execute().data[0]
    code_hash = bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode()
    fake_db.table("login_attempts").insert(
        {
            "user_id": user["id"],
            "code_hash": code_hash,
            "expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "max_attempts": 5,
            "attempts": 0,
        }
    ).execute()

    with pytest.raises(NotAuthorized):
        auth_service.verify_code("a@koyatalent.com", "123456")
