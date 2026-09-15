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
