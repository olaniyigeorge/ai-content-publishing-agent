"""Evidence-driven regeneration end to end: evaluation flags unsupported
claims -> gather_evidence searches + verifies real sources -> generate
regenerates with the evidence package -> pre-flight grounding validation ->
automatic evaluation. Covers requirement 12's full test list."""

from worker.firecrawl import SearchFailure
from worker.handlers import evaluate as evaluate_handler
from worker.handlers import gather_evidence as gather_evidence_handler
from worker.handlers import generate as generate_handler
from worker.handlers.gather_evidence import (
    _excerpt_is_verbatim,
    _infer_publisher,
    _infer_source_type,
)

REQUEST_ID = "00000000-0000-0000-0000-000000000060"
DRAFT_ID = "00000000-0000-0000-0000-000000000061"
PLAN_ID = "00000000-0000-0000-0000-000000000062"

_VALID_BODY = (
    "# A Real Article Title\n\n"
    + "This is a well-formed paragraph of the article body. " * 60
    + "\n\nSee the [source](https://example.com/source) for more.\n"
)


def _seed_request(fake_db):
    fake_db.table("content_requests").insert(
        {
            "id": REQUEST_ID,
            "status": "evaluating",
            "raw_idea": "why small agencies are moving to productized services",
            "target_audience": "B2B marketing leads at small agencies",
        }
    ).execute()


def _seed_draft(fake_db, **overrides):
    _seed_request(fake_db)
    row = {
        "id": DRAFT_ID,
        "content_request_id": REQUEST_ID,
        "title": "Draft",
        "body_markdown": _VALID_BODY,
        "version": 1,
        "option_label": "A",
        "source_ids_used": [],
        "status": "draft",
    }
    row.update(overrides)
    fake_db.table("article_drafts").insert(row).execute()


# --- unit tests: the mechanical anti-hallucination checks -----------------


def test_excerpt_is_verbatim_accepts_a_real_substring():
    raw = "Some intro text. The 42% figure comes from a 2026 industry survey of small agencies. More text."
    assert _excerpt_is_verbatim("The 42% figure comes from a 2026 industry survey of small agencies.", raw)


def test_excerpt_is_verbatim_rejects_a_fabricated_excerpt():
    """Requirement 4/5: a source must not be trusted merely because a model
    claims support — the excerpt must actually be in the retrieved content."""
    raw = "This page is actually about an unrelated topic and never mentions the claim at all."
    assert not _excerpt_is_verbatim("Agencies moving to productized services grew 42% in 2026.", raw)


def test_infer_source_type_and_publisher():
    assert _infer_source_type("https://www.forbes.com/some-article") == "news"
    assert _infer_source_type("https://blog.example.com/post") == "blog"
    assert _infer_source_type("https://nces.gov/report") == "official"
    assert _infer_source_type("https://randomsite.example.com/x") == "web_article"
    assert _infer_publisher("https://www.altagency.com/post") == "Altagency"


# --- gather_evidence handler -----------------------------------------------


def test_verified_source_supporting_a_previously_unsupported_claim(fake_db, monkeypatch):
    """Requirement 12: 'verified source supporting a previously unsupported
    claim' — a real search result, verified as actually supporting the
    claim, becomes part of the evidence package and a persisted source."""
    _seed_draft(fake_db)
    claim = "front-loaded setup costs mean agencies don't break even until month four"

    def fake_search_web(query, limit=3):
        assert claim in query
        return [
            {
                "url": "https://example.com/agency-retainer-report",
                "title": "The Truth About Agency Retainers",
                "raw_content": (
                    "Most agencies don't actually break even until month four because setup costs are "
                    "front-loaded and clients often leave around month six to eight."
                ),
            }
        ]

    def fake_verify(*, claim_text, source_title, source_url, source_content):
        assert claim_text == claim
        return {
            "supports_claim": True,
            "excerpt": "Most agencies don't actually break even until month four because setup costs are "
            "front-loaded",
            "reason": "directly states the break-even timing claim",
        }

    monkeypatch.setattr(gather_evidence_handler, "search_web", fake_search_web)
    monkeypatch.setattr(gather_evidence_handler.claude_service, "verify_claim_evidence", fake_verify)

    gather_evidence_handler.handle_gather_evidence(
        {"reference_id": DRAFT_ID, "payload": {"claims": [claim], "revision_instructions": "fix it"}}
    )

    jobs = fake_db.table("jobs").select("*").eq("job_type", "generate").execute().data
    assert len(jobs) == 1
    payload = jobs[0]["payload"]
    assert payload["escalated_model"] is not None
    assert len(payload["evidence_package"]) == 1
    evidence = payload["evidence_package"][0]
    assert evidence["claim_text"] == claim
    assert evidence["url"] == "https://example.com/agency-retainer-report"
    assert evidence["publisher"]
    assert evidence["source_type"]
    assert evidence["supported_claim"] == claim
    assert payload["claims_to_address"] == []

    sources = fake_db.table("sources").select("*").eq("content_request_id", REQUEST_ID).execute().data
    assert len(sources) == 1
    assert sources[0]["status"] == "selected"
    assert sources[0]["confidence"] == "strong"


def test_source_found_but_evidence_does_not_support_the_claim(fake_db, monkeypatch):
    """Requirement 12: 'source found but evidence does not support the
    claim' — the verifier says no, or claims support with a fabricated
    excerpt; either way it must not enter the evidence package."""
    _seed_draft(fake_db)
    claim = "productized services outperform retainers on every metric"

    def fake_search_web(query, limit=3):
        return [{"url": "https://example.com/unrelated", "title": "Unrelated", "raw_content": "Nothing relevant here."}]

    def fake_verify(*, claim_text, source_title, source_url, source_content):
        return {"supports_claim": False, "excerpt": "", "reason": "off-topic"}

    monkeypatch.setattr(gather_evidence_handler, "search_web", fake_search_web)
    monkeypatch.setattr(gather_evidence_handler.claude_service, "verify_claim_evidence", fake_verify)

    gather_evidence_handler.handle_gather_evidence(
        {"reference_id": DRAFT_ID, "payload": {"claims": [claim]}}
    )

    jobs = fake_db.table("jobs").select("*").eq("job_type", "generate").execute().data
    payload = jobs[0]["payload"]
    assert payload["evidence_package"] == []
    assert len(payload["claims_to_address"]) == 1
    assert payload["claims_to_address"][0]["claim_text"] == claim
    assert fake_db.table("sources").select("*").execute().data == []


def test_verifier_claims_support_with_a_fabricated_excerpt_is_discarded(fake_db, monkeypatch):
    """Mechanical enforcement of requirement 4: even if the verification
    model says supports_claim=True, a claimed excerpt that isn't actually in
    the source's real content must be rejected, not trusted at face value."""
    _seed_draft(fake_db)
    claim = "agencies lose most clients by month eight"

    def fake_search_web(query, limit=3):
        return [{"url": "https://example.com/real", "title": "Real Source", "raw_content": "Completely different content with no matching figures."}]

    def fake_verify(*, claim_text, source_title, source_url, source_content):
        return {
            "supports_claim": True,
            "excerpt": "This sentence was never actually in the source content at all.",
            "reason": "claims support",
        }

    monkeypatch.setattr(gather_evidence_handler, "search_web", fake_search_web)
    monkeypatch.setattr(gather_evidence_handler.claude_service, "verify_claim_evidence", fake_verify)

    gather_evidence_handler.handle_gather_evidence(
        {"reference_id": DRAFT_ID, "payload": {"claims": [claim]}}
    )

    jobs = fake_db.table("jobs").select("*").eq("job_type", "generate").execute().data
    assert jobs[0]["payload"]["evidence_package"] == []
    assert len(jobs[0]["payload"]["claims_to_address"]) == 1
    assert fake_db.table("sources").select("*").execute().data == []


def test_no_source_found(fake_db, monkeypatch):
    """Requirement 12: 'no source found' — search comes back empty (or
    fails outright); the claim ends up unresolved, no crash."""
    _seed_draft(fake_db)
    claim = "a claim nobody has written about"

    def fake_search_web(query, limit=3):
        return []

    monkeypatch.setattr(gather_evidence_handler, "search_web", fake_search_web)

    gather_evidence_handler.handle_gather_evidence(
        {"reference_id": DRAFT_ID, "payload": {"claims": [claim]}}
    )

    jobs = fake_db.table("jobs").select("*").eq("job_type", "generate").execute().data
    assert jobs[0]["payload"]["evidence_package"] == []
    assert jobs[0]["payload"]["claims_to_address"][0]["claim_text"] == claim


def test_search_failure_does_not_crash_the_handler(fake_db, monkeypatch):
    _seed_draft(fake_db)

    def fake_search_web(query, limit=3):
        raise SearchFailure("firecrawl down")

    monkeypatch.setattr(gather_evidence_handler, "search_web", fake_search_web)

    gather_evidence_handler.handle_gather_evidence(
        {"reference_id": DRAFT_ID, "payload": {"claims": ["some claim"]}}
    )

    jobs = fake_db.table("jobs").select("*").eq("job_type", "generate").execute().data
    assert len(jobs) == 1
    assert jobs[0]["payload"]["claims_to_address"][0]["claim_text"] == "some claim"


# --- evaluate -> gather_evidence handoff -----------------------------------


def test_regeneration_after_an_evaluation_with_unsupported_claims(fake_db, monkeypatch):
    """Requirement 12: 'regeneration after an evaluation' — evaluate's
    revise branch hands unsupported claims to gather_evidence with
    structured regeneration requirements, not free-form text alone."""
    _seed_draft(fake_db, version=1, source_ids_used=["00000000-0000-0000-0000-000000000099"])
    result = {
        "overall_status": "revise",
        "rubric_scores": {"source_grounding": 4},
        "overall_score": 3.0,
        "unsupported_claims": ["agencies always break even by month two"],
        "sections_to_revise": ["body"],
        "recommended_changes": ["remove or support the break-even claim"],
        "feedback": "one overstated claim",
    }
    monkeypatch.setattr(evaluate_handler.claude_service, "evaluate_draft", lambda **kw: result)

    evaluate_handler.handle_evaluate({"reference_id": DRAFT_ID, "payload": {}})

    jobs = fake_db.table("jobs").select("*").eq("job_type", "gather_evidence").execute().data
    assert len(jobs) == 1
    payload = jobs[0]["payload"]
    assert payload["claims"] == ["agencies always break even by month two"]
    requirements = payload["regeneration_requirements"]
    assert requirements["claims_needing_research"][0]["claim_text"] == "agencies always break even by month two"
    assert any(d["type"] == "unsupported_claim" for d in requirements["defects"])
    assert any(d["type"] == "section_weak" for d in requirements["defects"])


# --- generate: pre-flight validation + revision cap ------------------------


def _seed_generate_target(fake_db, *, version, source_ids_used=None):
    _seed_request(fake_db)
    fake_db.table("content_plans").insert(
        {"id": PLAN_ID, "content_request_id": REQUEST_ID, "outline": {}, "target_keywords": []}
    ).execute()
    fake_db.table("article_drafts").insert(
        {
            "id": DRAFT_ID,
            "content_request_id": REQUEST_ID,
            "content_plan_id": PLAN_ID,
            "option_label": "A",
            "version": version,
            "title": "Draft",
            "body_markdown": _VALID_BODY,
            "source_ids_used": source_ids_used or [],
            "status": "draft",
        }
    ).execute()


def test_grounding_validation_failure_triggers_direct_regeneration_below_cap(fake_db, monkeypatch):
    """Requirement 10: failed pre-flight validation regenerates directly
    (skipping the expensive evaluator), subject to the existing cap."""
    _seed_generate_target(fake_db, version=1)
    monkeypatch.setattr(
        generate_handler.claude_service,
        "generate_draft",
        lambda **kw: "# Title\n\nCites a [source](https://not-a-real-source.example.com/made-up).",
    )

    generate_handler.handle_generate(
        {"reference_type": "article_draft", "reference_id": DRAFT_ID, "payload": {}}
    )

    jobs = fake_db.table("jobs").select("*").execute().data
    assert not any(j["job_type"] == "evaluate" for j in jobs)
    generate_jobs = [j for j in jobs if j["job_type"] == "generate"]
    assert len(generate_jobs) == 1
    assert "fabricated_url" in generate_jobs[0]["payload"]["revision_instructions"]

    events = fake_db.table("stage_events").select("*").eq("stage", "grounding_validation").execute().data
    assert len(events) == 1
    assert events[0]["status"] == "failed"


def test_grounding_validation_failure_at_cap_still_proceeds_to_evaluation(fake_db, monkeypatch):
    """Requirement 10 + 12's 'revision-cap behavior': once the cap is hit,
    a still-failing draft goes to the real evaluator anyway rather than
    looping forever, mirroring evaluate.py's own at-cap behavior."""
    from app.config import get_settings

    settings = get_settings()
    _seed_generate_target(fake_db, version=settings.max_revisions)
    monkeypatch.setattr(
        generate_handler.claude_service,
        "generate_draft",
        lambda **kw: "# Title\n\nCites a [source](https://not-a-real-source.example.com/made-up).",
    )

    generate_handler.handle_generate(
        {"reference_type": "article_draft", "reference_id": DRAFT_ID, "payload": {}}
    )

    jobs = fake_db.table("jobs").select("*").execute().data
    assert any(j["job_type"] == "evaluate" for j in jobs)
    assert not any(j["job_type"] == "generate" for j in jobs)


def test_grounding_validation_passes_a_clean_draft_through_to_evaluation(fake_db, monkeypatch):
    _seed_generate_target(fake_db, version=1)
    fake_db.table("sources").insert(
        {
            "id": "00000000-0000-0000-0000-000000000098",
            "content_request_id": REQUEST_ID,
            "url": "https://example.com/source",
            "excerpt_selected": "This is the real excerpt content that was actually fetched from the source.",
            "retrieval_method": "url_provided",
            "status": "selected",
            "confidence": "strong",
        }
    ).execute()
    monkeypatch.setattr(
        generate_handler.claude_service,
        "generate_draft",
        lambda **kw: _VALID_BODY,
    )

    generate_handler.handle_generate(
        {"reference_type": "article_draft", "reference_id": DRAFT_ID, "payload": {}}
    )

    jobs = fake_db.table("jobs").select("*").execute().data
    assert any(j["job_type"] == "evaluate" for j in jobs)
    assert not any(j["job_type"] == "generate" for j in jobs)


def test_generate_passes_evidence_package_and_claims_to_address_through(fake_db, monkeypatch):
    """Requirement 5/7: the generator receives the verified evidence package
    and the still-unresolved claims explicitly, not just a prose string."""
    _seed_generate_target(fake_db, version=2)
    seen = {}

    def fake_generate_draft(**kwargs):
        seen.update(kwargs)
        return _VALID_BODY

    monkeypatch.setattr(generate_handler.claude_service, "generate_draft", fake_generate_draft)

    evidence_package = [
        {
            "claim_text": "agencies churn by month six",
            "claim_type": "supported_fact",
            "source_id": "src-1",
            "source_title": "Report",
            "publisher": "Example",
            "url": "https://example.com/report",
            "source_type": "web_article",
            "excerpt": "agencies churn by month six",
            "supported_claim": "agencies churn by month six",
        }
    ]
    claims_to_address = [
        {"claim_text": "unverifiable claim", "claim_type": "unsupported", "instruction": "hedge or remove"}
    ]

    generate_handler.handle_generate(
        {
            "reference_type": "article_draft",
            "reference_id": DRAFT_ID,
            "payload": {
                "revision_instructions": "fix it",
                "evidence_package": evidence_package,
                "claims_to_address": claims_to_address,
                "escalated_model": "claude-opus-5",
            },
        }
    )

    assert seen["evidence_package"] == evidence_package
    assert seen["claims_to_address"] == claims_to_address
    assert seen["model"] == "claude-opus-5"


# --- version lineage through the evidence-driven path ----------------------


def test_regeneration_from_a_non_latest_version_through_evidence_gathering(fake_db, monkeypatch):
    """Requirement 12: 'regeneration from a non-latest version' — explicitly
    regenerating from an older version (not the current latest) while going
    through gather_evidence still preserves lineage: new version allocated
    from the true max, parent points at the explicit source, and the newer
    sibling is left untouched."""
    _seed_request(fake_db)
    fake_db.table("content_plans").insert(
        {"id": PLAN_ID, "content_request_id": REQUEST_ID, "outline": {}, "target_keywords": []}
    ).execute()
    v4_id = "00000000-0000-0000-0000-000000000070"
    v5_id = "00000000-0000-0000-0000-000000000071"
    fake_db.table("article_drafts").insert(
        {
            "id": v4_id,
            "content_request_id": REQUEST_ID,
            "content_plan_id": PLAN_ID,
            "option_label": "A",
            "version": 4,
            "title": "V4",
            "body_markdown": _VALID_BODY,
            "source_ids_used": [],
            "status": "discarded",
        }
    ).execute()
    fake_db.table("article_drafts").insert(
        {
            "id": v5_id,
            "content_request_id": REQUEST_ID,
            "content_plan_id": PLAN_ID,
            "option_label": "A",
            "version": 5,
            "parent_draft_id": v4_id,
            "title": "V5",
            "body_markdown": _VALID_BODY,
            "source_ids_used": [],
            "status": "evaluated",
        }
    ).execute()

    monkeypatch.setattr(gather_evidence_handler, "search_web", lambda query, limit=3: [])
    gather_evidence_handler.handle_gather_evidence(
        {"reference_id": v4_id, "payload": {"claims": ["some claim"], "revision_instructions": "regen from v4"}}
    )

    gen_job = fake_db.table("jobs").select("*").eq("job_type", "generate").execute().data[0]
    assert gen_job["reference_id"] == v4_id

    monkeypatch.setattr(generate_handler.claude_service, "generate_draft", lambda **kw: _VALID_BODY)
    generate_handler.handle_generate(
        {"reference_type": "article_draft", "reference_id": v4_id, "payload": gen_job["payload"]}
    )

    drafts = fake_db.table("article_drafts").select("*").eq("content_request_id", REQUEST_ID).execute().data
    versions = {d["version"]: d for d in drafts}
    assert set(versions) == {4, 5, 6}
    assert versions[6]["parent_draft_id"] == v4_id
    assert versions[5]["status"] == "evaluated"  # untouched
    assert versions[5]["body_markdown"] == _VALID_BODY
