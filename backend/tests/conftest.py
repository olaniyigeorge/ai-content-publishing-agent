import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("FIRECRAWL_API_KEY", "test")

import pytest

from tests.fake_supabase import FakeSupabase


@pytest.fixture()
def fake_db(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr("db.client.get_supabase", lambda: fake)
    # every module that did `from db.client import get_supabase` at import
    # time needs patching at its own reference too
    for module in [
        "app.services.intake_service",
        "app.services.review_service",
        "app.services.request_state_service",
        "app.api.publishing",
        "auth.service",
        "worker.handlers.research",
        "worker.handlers.plan",
        "worker.handlers.generate",
        "worker.handlers.evaluate",
        "worker.handlers.adapt",
        "worker.handlers.publish",
        "worker.main",
        "worker.claim",
    ]:
        try:
            monkeypatch.setattr(f"{module}.get_supabase", lambda: fake)
        except (ModuleNotFoundError, AttributeError):
            pass
    return fake
