"""worker/handlers/research.py — TESTING_FINDINGS.md, 2026-09-16: a failed
scrape must show up on the Sources list with a reason (not just in
stage_events), and a malformed Claude source-selection response must raise a
clear error rather than a bare KeyError."""

import pytest

from shared.errors import ResearchFailure
from worker.firecrawl import ScrapeFailure
from worker.handlers import research as research_handler

REQUEST_ID = "00000000-0000-0000-0000-000000000060"
ATTACHMENT_ID = "00000000-0000-0000-0000-000000000061"


def _seed(fake_db):
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "raw_idea": "idea", "target_audience": "marketers"}
    ).execute()
    fake_db.table("intake_attachments").insert(
        {"id": ATTACHMENT_ID, "content_request_id": REQUEST_ID, "type": "url", "url": "https://dead-link.example"}
    ).execute()


def test_failed_scrape_gets_a_visible_source_row_with_reason(fake_db, monkeypatch):
    _seed(fake_db)

    def fake_scrape(url, **kw):
        raise ScrapeFailure(f"Firecrawl returned 404 for {url}")

    monkeypatch.setattr(research_handler, "scrape_url", fake_scrape)

    research_handler.handle_research({"reference_id": REQUEST_ID, "payload": {"attachment_ids": [ATTACHMENT_ID]}})

    sources = fake_db.table("sources").select("*").eq("content_request_id", REQUEST_ID).execute().data
    assert len(sources) == 1
    assert sources[0]["status"] == "failed"
    assert "404" in sources[0]["discard_reason"]


def test_malformed_source_selection_response_raises_clear_error(fake_db, monkeypatch):
    _seed(fake_db)
    monkeypatch.setattr(research_handler, "scrape_url", lambda url, **kw: {"title": "T", "raw_content": "real text"})
    monkeypatch.setattr(research_handler.claude_service, "select_sources", lambda **kw: {})  # "sources" key omitted

    with pytest.raises(ResearchFailure, match="sources"):
        research_handler.handle_research({"reference_id": REQUEST_ID, "payload": {"attachment_ids": [ATTACHMENT_ID]}})
