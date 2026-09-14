"""Scenario 6 + EDGE_CASES.md #31, #33, #37 — each channel gets its own
adaptation call, plain_text for linkedin/x, html for newsletter, and a
per-channel failure doesn't take down the others."""

from claude.outputs import ADAPTATION_SCHEMA
from worker.handlers import adapt as adapt_handler

REQUEST_ID = "00000000-0000-0000-0000-000000000040"
DRAFT_ID = "00000000-0000-0000-0000-000000000041"


def test_adaptation_schema_requires_content_format_and_formatting_check():
    assert set(ADAPTATION_SCHEMA["required"]) == {"content", "content_format", "formatting_check"}
    assert ADAPTATION_SCHEMA["properties"]["content_format"]["enum"] == ["plain_text", "html"]


def _fake_result_for(channel: str) -> dict:
    if channel == "newsletter":
        return {"content": "<h2>Subject</h2><p>body</p>", "content_format": "html", "formatting_check": {"word_count": 300}}
    return {"content": f"a {channel} post, no markdown", "content_format": "plain_text", "formatting_check": {"char_count": 100}}


def test_all_three_channels_get_distinct_content_and_correct_format(fake_db, monkeypatch):
    fake_db.table("article_drafts").insert(
        {"id": DRAFT_ID, "content_request_id": REQUEST_ID, "title": "T", "body_markdown": "body"}
    ).execute()
    fake_db.table("content_requests").insert({"id": REQUEST_ID, "target_audience": "marketers"}).execute()
    monkeypatch.setattr(
        adapt_handler.claude_service, "adapt_for_channel", lambda channel, **kw: _fake_result_for(channel)
    )

    adapt_handler.handle_adapt({"reference_id": DRAFT_ID})

    adaptations = fake_db.table("channel_adaptations").select("*").eq("content_request_id", REQUEST_ID).execute().data
    by_channel = {a["channel"]: a for a in adaptations}
    assert len(by_channel) == 3
    assert by_channel["linkedin"]["content_format"] == "plain_text"
    assert by_channel["x"]["content_format"] == "plain_text"
    assert by_channel["newsletter"]["content_format"] == "html"
    contents = {a["content"] for a in adaptations}
    assert len(contents) == 3  # not the same text three times (EDGE_CASES.md #34)


def test_one_channel_failing_does_not_block_the_others(fake_db, monkeypatch):
    fake_db.table("article_drafts").insert(
        {"id": DRAFT_ID, "content_request_id": REQUEST_ID, "title": "T", "body_markdown": "body"}
    ).execute()
    fake_db.table("content_requests").insert({"id": REQUEST_ID, "target_audience": "marketers"}).execute()

    def flaky_adapt(channel, **kw):
        if channel == "x":
            raise RuntimeError("Claude error")
        return _fake_result_for(channel)

    monkeypatch.setattr(adapt_handler.claude_service, "adapt_for_channel", flaky_adapt)

    adapt_handler.handle_adapt({"reference_id": DRAFT_ID})

    adaptations = fake_db.table("channel_adaptations").select("*").eq("content_request_id", REQUEST_ID).execute().data
    assert {a["channel"] for a in adaptations} == {"linkedin", "newsletter"}
    events = fake_db.table("stage_events").select("*").eq("content_request_id", REQUEST_ID).execute().data
    assert any(e["status"] == "failed" and "x" in (e.get("error_message") or "") for e in events)
