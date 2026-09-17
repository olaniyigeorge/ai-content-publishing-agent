"""Evidence-driven regeneration: given a draft's specific unsupported
claims (flagged by the evaluator), search for real sources, verify each
candidate actually supports the claim before trusting it, and hand the
generator a verified evidence package — instead of hoping a free-form
"make it punchier"-style instruction produces real grounding on its own.

Nothing here invents a URL, title, or excerpt: every field in the evidence
package traces back to a real worker.firecrawl.search_web result, and every
claimed excerpt is checked to actually appear (near-verbatim) in that
result's own content before it's trusted — a verification model claiming
"this supports the claim" is not enough on its own (claude/prompts/
verify_evidence.py can still be wrong or overly generous); `_excerpt_is_
verbatim` is the mechanical backstop.
"""

from datetime import UTC, datetime
from difflib import SequenceMatcher
from urllib.parse import urlparse

import claude.service as claude_service
from claude.models import OPUS
from db.client import get_supabase
from shared.enums import (
    ClaimType,
    JobReferenceType,
    JobType,
    PipelineStage,
    RequestStatus,
    SourceConfidence,
    SourceRetrievalMethod,
    SourceStatus,
    StageEventStatus,
)
from worker.firecrawl import SearchFailure, search_web

CANDIDATES_PER_CLAIM = 3
EXCERPT_MATCH_THRESHOLD = 0.8

_OFFICIAL_TLDS = (".gov", ".edu")
_BLOG_HINTS = ("blog.", "/blog/", "medium.com", "substack.com")
_NEWS_HINTS = ("news.", "reuters.com", "apnews.com", "bloomberg.com", "nytimes.com", "wsj.com", "forbes.com")


def _infer_publisher(url: str) -> str:
    netloc = urlparse(url).netloc.removeprefix("www.")
    name = netloc.split(".")[0] if netloc else url
    return name.replace("-", " ").title() or netloc


def _infer_source_type(url: str) -> str:
    lowered = url.lower()
    stripped = lowered.split("?")[0].rstrip("/")
    if any(stripped.endswith(tld) or f"{tld}/" in lowered for tld in _OFFICIAL_TLDS):
        return "official"
    if any(hint in lowered for hint in _NEWS_HINTS):
        return "news"
    if any(hint in lowered for hint in _BLOG_HINTS):
        return "blog"
    return "web_article"


def _excerpt_is_verbatim(excerpt: str, raw_content: str) -> bool:
    """The verification model is asked to copy a real excerpt, not
    paraphrase — but a model claiming an excerpt exists doesn't make it so.
    This checks the claimed excerpt actually appears in the source's real
    retrieved content (allowing minor whitespace/quote-character drift, not
    a free semantic paraphrase)."""
    excerpt = " ".join((excerpt or "").split())
    raw_content = " ".join((raw_content or "").split())
    if not excerpt or len(excerpt) < 15:
        return False
    if excerpt.lower() in raw_content.lower():
        return True

    lowered_raw = raw_content.lower()
    lowered_excerpt = excerpt.lower()
    window = len(excerpt) + 40
    step = max(window // 2, 1)
    best = 0.0
    for i in range(0, max(len(lowered_raw) - window, 1) + 1, step):
        chunk = lowered_raw[i : i + window]
        best = max(best, SequenceMatcher(None, lowered_excerpt, chunk).ratio())
        if best >= EXCERPT_MATCH_THRESHOLD:
            return True
    return best >= EXCERPT_MATCH_THRESHOLD


def _gather_evidence_for_claim(db, *, request_id: str, claim_text: str) -> dict | None:
    """Searches for real sources and verifies each candidate actually
    supports the claim, returning the first verified evidence dict — or
    None if no candidate held up. Every field but the model's `reason`
    judgment traces back to a real search result; the verification call
    never supplies url/title itself, so it can't invent source metadata."""
    try:
        candidates = search_web(claim_text, limit=CANDIDATES_PER_CLAIM)
    except SearchFailure:
        return None

    for candidate in candidates:
        verification = claude_service.verify_claim_evidence(
            claim_text=claim_text,
            source_title=candidate.get("title"),
            source_url=candidate["url"],
            source_content=candidate["raw_content"],
        )
        if not verification.get("supports_claim"):
            continue
        excerpt = verification.get("excerpt") or ""
        if not _excerpt_is_verbatim(excerpt, candidate["raw_content"]):
            # The model claimed support, but the excerpt it gave isn't
            # actually in the source's real content — a source must not be
            # included merely because a URL exists and a model says so.
            continue

        source_row = (
            db.table("sources")
            .insert(
                {
                    "content_request_id": request_id,
                    "intake_attachment_id": None,
                    "url": candidate["url"],
                    "title": candidate.get("title"),
                    "raw_content": candidate["raw_content"],
                    "excerpt_selected": excerpt,
                    "relevance_notes": f"Verified evidence for a previously unsupported claim: {claim_text}",
                    "retrieval_method": SourceRetrievalMethod.WEB_SEARCH.value,
                    "status": SourceStatus.SELECTED.value,
                    "confidence": SourceConfidence.STRONG.value,
                    "retrieved_at": datetime.now(UTC).isoformat(),
                }
            )
            .execute()
            .data[0]
        )
        return {
            "claim_text": claim_text,
            "claim_type": ClaimType.SUPPORTED_FACT.value,
            "source_id": source_row["id"],
            "source_title": candidate.get("title") or _infer_publisher(candidate["url"]),
            "publisher": _infer_publisher(candidate["url"]),
            "url": candidate["url"],
            "source_type": _infer_source_type(candidate["url"]),
            "excerpt": excerpt,
            "supported_claim": claim_text,
        }
    return None


def handle_gather_evidence(job: dict) -> None:
    db = get_supabase()
    draft_id = job["reference_id"]
    payload = job["payload"]
    claims = payload.get("claims") or []

    draft = db.table("article_drafts").select("*").eq("id", draft_id).execute().data[0]
    request_id = draft["content_request_id"]

    evidence_package: list[dict] = []
    unresolved_claims: list[dict] = []
    for claim in claims:
        claim_text = claim if isinstance(claim, str) else claim.get("claim_text", "")
        if not claim_text:
            continue
        evidence = _gather_evidence_for_claim(db, request_id=request_id, claim_text=claim_text)
        if evidence:
            evidence_package.append(evidence)
        else:
            unresolved_claims.append(
                {
                    "claim_text": claim_text,
                    "claim_type": ClaimType.UNSUPPORTED.value,
                    "instruction": (
                        "no supporting evidence was found for this claim — rewrite it as a clearly hedged "
                        "inference/hypothesis, or remove it entirely; do not restate it as settled fact"
                    ),
                }
            )

    db.table("stage_events").insert(
        {
            "content_request_id": request_id,
            "stage": PipelineStage.EVIDENCE_GATHERING.value,
            "status": StageEventStatus.SUCCEEDED.value,
            "detail": {
                "draft_id": draft_id,
                "claims_checked": len(claims),
                "evidence_found": len(evidence_package),
                "unresolved": len(unresolved_claims),
            },
        }
    ).execute()

    db.table("content_requests").update(
        {"status": RequestStatus.REVISING.value, "updated_at": datetime.now(UTC).isoformat()}
    ).eq("id", request_id).execute()

    db.table("jobs").insert(
        {
            "job_type": JobType.GENERATE.value,
            "reference_type": JobReferenceType.ARTICLE_DRAFT.value,
            "reference_id": draft_id,
            "payload": {
                "revision_instructions": payload.get("revision_instructions"),
                "evidence_package": evidence_package,
                "claims_to_address": unresolved_claims,
                "escalated_model": OPUS,
            },
        }
    ).execute()
