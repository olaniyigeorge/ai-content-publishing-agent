"""Route-wiring smoke tests via FastAPI's TestClient — the audit flagged that
every other test hits service functions directly, so a broken dependency
wire-up or response_model mismatch wouldn't be caught anywhere."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_is_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_ready_reports_503_when_supabase_unreachable(monkeypatch):
    import app.main as main_module

    class BoomTable:
        def select(self, *_a, **_kw):
            return self

        def limit(self, *_a, **_kw):
            return self

        def execute(self):
            raise RuntimeError("connection refused")

    class BoomClient:
        def table(self, *_a, **_kw):
            return BoomTable()

    monkeypatch.setattr(main_module, "get_supabase", lambda: BoomClient())

    client = TestClient(app)
    resp = client.get("/health/ready")
    assert resp.status_code == 503


def test_protected_route_without_session_cookie_is_401():
    client = TestClient(app)
    resp = client.get("/api/requests")
    assert resp.status_code == 401


def test_protected_route_with_garbage_session_cookie_is_401(fake_db):
    client = TestClient(app)
    client.cookies.set("koya_session", "not-a-real-session")
    resp = client.get("/api/requests")
    assert resp.status_code == 401


def test_upload_endpoint_requires_auth():
    client = TestClient(app)
    resp = client.post("/api/uploads", files={"file": ("a.png", b"data", "image/png")})
    assert resp.status_code == 401


def test_create_access_rule_with_expiry_is_json_serializable(fake_db, monkeypatch):
    """Regression test: AccessRuleIn.model_dump() (without mode='json') left
    expires_at as a Python datetime, which the Supabase client's insert()
    tried to json.dumps() and raised TypeError. Caught by hand when the
    admin access-rules UI tried to grant access with an expiry set."""
    import auth.deps as auth_deps

    app.dependency_overrides[auth_deps.get_current_user] = lambda: {"id": "u1", "email": "a@koyatalent.com"}
    try:
        client = TestClient(app)
        resp = client.post(
            "/auth/access-rules",
            json={
                "type": "email",
                "value": "new-person@koyatalent.com",
                "enabled": True,
                "expires_at": "2027-01-01T00:00:00Z",
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["value"] == "new-person@koyatalent.com"
    finally:
        app.dependency_overrides.pop(auth_deps.get_current_user, None)
