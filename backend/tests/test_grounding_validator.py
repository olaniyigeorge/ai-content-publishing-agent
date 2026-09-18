"""Pre-flight grounding validator (claude/grounding_validator.py) — the cheap,
deterministic gate that runs on every generated draft before the expensive
per-draft evaluator. Covers the six detection categories the architecture
calls for: fabricated URLs, citation mismatches, quantitative paraphrase
drift, unsupported trend claims, unsupported causal claims, and unsupported
claims generally."""

from claude.grounding_validator import validate_grounding

SOURCES = [
    {
        "id": "s1",
        "url": "https://example.com/agency-retainer-report",
        "excerpt_selected": "A 2026 survey found that 42% of small agencies dropped retainer contracts within a year.",
    },
]


def test_passes_a_clean_draft_with_only_provided_citations():
    body = (
        "Small agencies are rethinking retainers. "
        "A 2026 survey found that 42% of small agencies dropped retainer contracts within a year "
        "([source](https://example.com/agency-retainer-report))."
    )
    result = validate_grounding(body_markdown=body, sources=SOURCES)
    assert result["passed"] is True
    assert result["violations"] == []


def test_fabricated_url_in_draft_is_flagged():
    """Requirement 12: 'fabricated URL in previous draft'."""
    body = (
        "Agencies are moving to productized services "
        "([source](https://not-a-real-source.example.com/made-up))."
    )
    result = validate_grounding(body_markdown=body, sources=SOURCES)
    assert result["passed"] is False
    assert any("fabricated_url" in v for v in result["violations"])


def test_unsupported_trend_claim_is_flagged():
    """Requirement 12: 'unsupported trend claim'."""
    body = "More and more agencies are abandoning retainers every quarter, with no sign of slowing down."
    result = validate_grounding(body_markdown=body, sources=SOURCES)
    assert result["passed"] is False
    assert any("unsupported_trend_claim" in v for v in result["violations"])


def test_numerical_paraphrase_drift_is_flagged():
    """Requirement 12: 'numerical paraphrase drift' — the draft states a
    different figure than what its own cited source excerpt actually says."""
    body = (
        "A 2026 survey found that 67% of small agencies dropped retainer contracts within a year "
        "([source](https://example.com/agency-retainer-report))."
    )
    result = validate_grounding(body_markdown=body, sources=SOURCES)
    assert result["passed"] is False
    assert any("quantitative_paraphrase_drift" in v for v in result["violations"])


def test_unsupported_productized_service_claim_is_flagged():
    """Requirement 12: 'unsupported productized-service claim' — a generic
    unhedged assertion-style claim with no citation nearby."""
    body = "Research shows that productized services always outperform retainers for small agencies."
    result = validate_grounding(body_markdown=body, sources=SOURCES)
    assert result["passed"] is False
    assert any("unsupported_claim" in v for v in result["violations"])


def test_citing_a_selected_but_never_fetched_source_is_still_fabricated():
    """TESTING_FINDINGS2.md, 2026-09-18: a source can be marked `selected`
    (override_source_status) without ever being successfully fetched — e.g.
    a reviewer clicking "mark selected" on a 403'd/failed source. It has no
    excerpt_selected. Citing it must still be caught as fabricated: there is
    no real content behind that URL to ground anything against, so treating
    it as "known" would let the model attribute any claim to it for free."""
    never_fetched_sources = [
        {"id": "s2", "url": "https://www.linkedin.com/business/marketing", "excerpt_selected": None},
    ]
    body = (
        "LinkedIn's algorithm favors dwell time on the platform "
        "([source](https://www.linkedin.com/business/marketing))."
    )
    result = validate_grounding(body_markdown=body, sources=never_fetched_sources)
    assert result["passed"] is False
    assert any("fabricated_url" in v for v in result["violations"])


def test_unsupported_causal_claim_is_flagged():
    body = "Front-loaded setup costs cause most agencies to abandon retainer contracts by month six."
    result = validate_grounding(body_markdown=body, sources=SOURCES)
    assert result["passed"] is False
    assert any("unsupported_causal_claim" in v for v in result["violations"])


def test_citation_mismatch_is_flagged():
    """A citation exists and points at a real provided source, but the
    citing sentence has no meaningful overlap with that source's excerpt —
    the link doesn't actually back what's being said next to it."""
    body = (
        "Our new office espresso machine has three brew settings "
        "([source](https://example.com/agency-retainer-report))."
    )
    result = validate_grounding(body_markdown=body, sources=SOURCES)
    assert result["passed"] is False
    assert any("citation_mismatch" in v for v in result["violations"])


def test_hedged_claim_with_no_citation_does_not_trip_trend_or_causal_checks():
    """A claim phrased as the writer's own observation, without trend/causal/
    assertion trigger language, shouldn't be flagged just for lacking a link —
    the validator targets specific unhedged patterns, not every uncited sentence."""
    body = "Retainers can feel restrictive for a small team juggling several clients at once."
    result = validate_grounding(body_markdown=body, sources=SOURCES)
    assert result["passed"] is True


def test_digits_in_the_cited_url_itself_do_not_trip_quantitative_drift():
    """A real, recurring false positive: a URL slug/article-id containing
    digits (e.g. '.../article/158957-resource-poor-risk-rich...') was being
    read as if the sentence itself stated the number 158957, which then
    never matched the excerpt — flagging every draft that cited this exact
    URL, no matter how the surrounding prose was reworded across three
    regenerations in a row (2026-09-17 report: the model correctly addressed
    every other flagged issue but this one recurred identically every time,
    because it was never actually about anything the model wrote)."""
    sources = [
        {
            "id": "s2",
            "url": "https://jsbs.scholasticahq.com/article/158957-resource-poor-risk-rich",
            "excerpt_selected": "There is a fundamental misalignment between the capabilities AI strategy "
            "requires and the limited resources available to most small businesses.",
        }
    ]
    body = (
        "There is a fundamental misalignment between what AI strategy requires and what small "
        "businesses can actually resource "
        "([study](https://jsbs.scholasticahq.com/article/158957-resource-poor-risk-rich))."
    )
    result = validate_grounding(body_markdown=body, sources=sources)
    assert result["passed"] is True
    assert result["violations"] == []
