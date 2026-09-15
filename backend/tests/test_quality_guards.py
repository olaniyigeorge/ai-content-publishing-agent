"""claude/quality_guards.py — deterministic checks that don't trust the
model's self-reported formatting_check / rubric pass."""

from claude.quality_guards import (
    check_article,
    check_channel_adaptation,
    truncate_to_limit,
)
from worker.handlers import adapt as adapt_handler

REQUEST_ID = "00000000-0000-0000-0000-000000000050"
DRAFT_ID = "00000000-0000-0000-0000-000000000051"


def test_check_article_flags_short_body_missing_h1_and_no_links():
    result = check_article("just a sentence, no heading, no links")
    assert result["has_h1"] is False
    assert result["link_count"] == 0
    assert any("too short" in v for v in result["violations"])
    assert any("H1" in v for v in result["violations"])


def test_check_article_passes_well_formed_body():
    body = "# Title\n\n" + "A solid sentence of real content. " * 60 + "\n[source](https://example.com)\n"
    result = check_article(body)
    assert result["violations"] == []


def test_check_channel_adaptation_catches_oversized_x_post():
    result = check_channel_adaptation(channel="x", content="x" * 300, content_format="plain_text")
    assert result["within_limit"] is False
    assert any("281" in v or "300" in v for v in result["violations"])


def test_check_channel_adaptation_catches_undersized_newsletter():
    result = check_channel_adaptation(channel="newsletter", content="too short", content_format="plain_text")
    assert result["within_limit"] is False


def test_check_channel_adaptation_strips_html_before_counting():
    result = check_channel_adaptation(
        channel="x", content="<p>" + ("word " * 5) + "</p>", content_format="html"
    )
    assert result["word_count"] == 5


def test_truncate_to_limit_returns_unmodified_when_already_within_limit():
    # non-chars channel (newsletter) has no truncation fallback
    assert truncate_to_limit("short", "newsletter") is None


def test_truncate_to_limit_drops_trailing_hashtags_first():
    content = "A real, useful point worth reading. " + " ".join(f"#tag{i}" for i in range(40))
    trimmed = truncate_to_limit(content, "x")
    assert trimmed is not None
    assert len(trimmed) <= 280
    assert trimmed.startswith("A real, useful point worth reading.")


def test_truncate_to_limit_hard_trims_at_word_boundary_when_no_hashtags():
    content = "A meaningful sentence about the article. " * 20
    trimmed = truncate_to_limit(content, "x")
    assert trimmed is not None
    assert len(trimmed) <= 280
    assert not trimmed.endswith(" ")


def test_truncate_to_limit_returns_none_when_nothing_viable_survives():
    # a two-character body followed by one giant hashtag: stripping the
    # hashtag leaves far less than MIN_VIABLE_CHARS
    content = "ok #" + "x" * 300
    assert truncate_to_limit(content, "x") is None


def test_adapt_handler_truncates_oversized_x_post_and_approves(fake_db, monkeypatch):
    fake_db.table("article_drafts").insert(
        {"id": DRAFT_ID, "content_request_id": REQUEST_ID, "title": "T", "body_markdown": "body"}
    ).execute()
    fake_db.table("content_requests").insert({"id": REQUEST_ID, "target_audience": "marketers"}).execute()

    def oversized_x(channel, **kw):
        content = "A meaningful sentence about the article. " * 20 if channel == "x" else f"a {channel} post"
        return {"content": content, "content_format": "plain_text", "formatting_check": {"within_limit": True}}

    monkeypatch.setattr(adapt_handler.claude_service, "adapt_for_channel", oversized_x)

    adapt_handler.handle_adapt({"reference_id": DRAFT_ID})

    adaptations = fake_db.table("channel_adaptations").select("*").eq("content_request_id", REQUEST_ID).execute().data
    by_channel = {a["channel"]: a for a in adaptations}
    assert by_channel["x"]["status"] == "approved"
    assert len(by_channel["x"]["content"]) <= 280
    assert by_channel["x"]["formatting_check"]["within_limit"] is True
    assert by_channel["x"]["formatting_check"]["auto_trimmed"] is True

    queue = fake_db.table("publishing_queue").select("*").execute().data
    queued_adaptation_ids = {q["channel_adaptation_id"] for q in queue}
    assert by_channel["x"]["id"] in queued_adaptation_ids  # truncated post still gets queued


def test_adapt_handler_marks_unviable_oversized_channel_as_failed_not_published(fake_db, monkeypatch):
    fake_db.table("article_drafts").insert(
        {"id": DRAFT_ID, "content_request_id": REQUEST_ID, "title": "T", "body_markdown": "body"}
    ).execute()
    fake_db.table("content_requests").insert({"id": REQUEST_ID, "target_audience": "marketers"}).execute()

    def oversized_x(channel, **kw):
        content = "ok #" + "x" * 300 if channel == "x" else f"a {channel} post"
        return {"content": content, "content_format": "plain_text", "formatting_check": {"within_limit": True}}

    monkeypatch.setattr(adapt_handler.claude_service, "adapt_for_channel", oversized_x)

    adapt_handler.handle_adapt({"reference_id": DRAFT_ID})

    adaptations = fake_db.table("channel_adaptations").select("*").eq("content_request_id", REQUEST_ID).execute().data
    by_channel = {a["channel"]: a for a in adaptations}
    assert by_channel["x"]["status"] == "failed"
    assert by_channel["x"]["formatting_check"]["within_limit"] is False  # real check overrides self-report
    assert by_channel["linkedin"]["status"] == "approved"

    events = fake_db.table("stage_events").select("*").eq("content_request_id", REQUEST_ID).execute().data
    assert any("x" in (e.get("error_message") or "") and "character" in (e.get("error_message") or "") for e in events)

    queue = fake_db.table("publishing_queue").select("*").execute().data
    queued_adaptation_ids = {q["channel_adaptation_id"] for q in queue}
    assert by_channel["x"]["id"] not in queued_adaptation_ids  # never queued for publish
