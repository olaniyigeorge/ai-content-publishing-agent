"""Scenario 3 + EDGE_CASES.md #43 — a generated draft's source_ids_used must
point at real sources.id rows, not an empty or fabricated list."""

from worker.handlers import generate as generate_handler

REQUEST_ID = "00000000-0000-0000-0000-000000000030"
PLAN_ID = "00000000-0000-0000-0000-000000000031"
SOURCE_ID = "00000000-0000-0000-0000-000000000032"


def test_generated_draft_source_ids_used_trace_to_real_sources(fake_db, monkeypatch):
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "raw_idea": "idea", "target_audience": "marketers"}
    ).execute()
    fake_db.table("content_plans").insert(
        {"id": PLAN_ID, "content_request_id": REQUEST_ID, "outline": {"sections": []}, "target_keywords": []}
    ).execute()
    fake_db.table("sources").insert(
        {
            "id": SOURCE_ID,
            "content_request_id": REQUEST_ID,
            "url": "https://example.com",
            "excerpt_selected": "a real stat",
            "relevance_notes": "supports the main claim",
            "retrieval_method": "url_provided",
            "status": "selected",
        }
    ).execute()
    monkeypatch.setattr(generate_handler.claude_service, "generate_draft", lambda **kw: "# Title\n\nbody text")

    job = {
        "reference_type": "content_request",
        "reference_id": REQUEST_ID,
        "payload": {"content_plan_id": PLAN_ID, "option_label": "A"},
    }
    generate_handler.handle_generate(job)

    draft = fake_db.table("article_drafts").select("*").eq("content_request_id", REQUEST_ID).execute().data[0]
    assert draft["source_ids_used"] == [SOURCE_ID]  # traceable, not empty (EDGE_CASES.md #43)


def test_generated_draft_with_no_selected_sources_has_empty_but_honest_list(fake_db, monkeypatch):
    """No selected sources (e.g. all failed retrieval) shouldn't be masked —
    source_ids_used should be an honest empty list, not fabricated."""
    fake_db.table("content_requests").insert(
        {"id": REQUEST_ID, "raw_idea": "idea with no sources", "target_audience": "marketers"}
    ).execute()
    fake_db.table("content_plans").insert(
        {"id": PLAN_ID, "content_request_id": REQUEST_ID, "outline": {"sections": []}, "target_keywords": []}
    ).execute()
    monkeypatch.setattr(generate_handler.claude_service, "generate_draft", lambda **kw: "# Title\n\nbody text")

    job = {
        "reference_type": "content_request",
        "reference_id": REQUEST_ID,
        "payload": {"content_plan_id": PLAN_ID, "option_label": "A"},
    }
    generate_handler.handle_generate(job)

    draft = fake_db.table("article_drafts").select("*").eq("content_request_id", REQUEST_ID).execute().data[0]
    assert draft["source_ids_used"] == []
