from datetime import UTC, datetime

import claude.service as claude_service
from claude.outputs import require_fields
from db.client import get_supabase
from shared.enums import (
    JobReferenceType,
    JobType,
    PipelineStage,
    RequestStatus,
    SourceConfidence,
    SourceRetrievalMethod,
    SourceStatus,
    StageEventStatus,
)
from shared.errors import ResearchFailure
from worker.firecrawl import ScrapeFailure, SearchFailure, scrape_url, search_web

SEARCH_RESULT_LIMIT = 3


def _select_and_store_sources(
    db,
    *,
    request_row: dict,
    source_rows: list[dict],
    research_focus: str | None = None,
) -> int:
    """Runs claude_service.select_sources over freshly-retrieved source rows
    and writes the selected/discarded status, excerpt, and confidence back
    onto each row. Shared by the initial research pass and a later gap-fill
    pass so both mark thin evidence the same way instead of one path
    trusting everything it finds. Returns the usable-source count."""
    if not source_rows:
        return 0

    selection = claude_service.select_sources(
        raw_idea=request_row["raw_idea"],
        target_audience=request_row["target_audience"],
        sources=source_rows,
        research_focus=research_focus,
    )
    require_fields(selection, ["sources"], step="source selection", error_cls=ResearchFailure)
    by_id = {s["source_id"]: s for s in selection["sources"] if "source_id" in s}

    usable_count = 0
    for row in source_rows:
        picked = by_id.get(row["id"])
        if not picked:
            continue
        if not picked.get("usable"):
            db.table("sources").update(
                {
                    "status": SourceStatus.DISCARDED.value,
                    "discard_reason": picked.get("unusable_reason") or "no usable article text",
                }
            ).eq("id", row["id"]).execute()
            continue
        usable_count += 1
        confidence = picked.get("confidence") or SourceConfidence.STRONG.value
        db.table("sources").update(
            {
                "excerpt_selected": picked.get("excerpt_selected"),
                "relevance_notes": picked.get("relevance_notes"),
                "status": SourceStatus.SELECTED.value,
                "confidence": confidence,
                "confidence_reason": picked.get("confidence_reason") if confidence == SourceConfidence.THIN.value else None,
            }
        ).eq("id", row["id"]).execute()
    return usable_count


def handle_research(job: dict) -> None:
    """EDGE_CASES.md #6: if every source fails to retrieve, this must be
    visible — the pipeline still proceeds (a raw_idea alone is a valid
    request per scenario 1) but stage_events records zero usable sources so
    a human/reviewer can see the gap, not just an article with no grounding.
    """
    if job["payload"].get("gap_fill_for_draft_id"):
        _handle_gap_fill_research(job)
        return

    db = get_supabase()
    request_id = job["reference_id"]
    attachment_ids = job["payload"].get("attachment_ids", [])

    request_row = db.table("content_requests").select("*").eq("id", request_id).execute().data[0]
    attachments = (
        db.table("intake_attachments").select("*").in_("id", attachment_ids).execute().data if attachment_ids else []
    )

    source_rows = []
    failures = []
    for attachment in attachments:
        try:
            scraped = scrape_url(attachment["url"])
        except ScrapeFailure as exc:
            failures.append({"url": attachment["url"], "error": str(exc)})
            # A failed scrape used to only show up in stage_events.detail —
            # invisible on the Sources list a reviewer actually looks at. It
            # still gets a row, just as `failed` with the reason attached
            # (TESTING_FINDINGS.md, 2026-09-16).
            db.table("sources").insert(
                {
                    "content_request_id": request_id,
                    "intake_attachment_id": attachment["id"],
                    "url": attachment["url"],
                    "retrieval_method": SourceRetrievalMethod.URL_PROVIDED.value,
                    "status": SourceStatus.FAILED.value,
                    "discard_reason": str(exc),
                }
            ).execute()
            continue
        source_rows.append(
            db.table("sources")
            .insert(
                {
                    "content_request_id": request_id,
                    "intake_attachment_id": attachment["id"],
                    "url": attachment["url"],
                    "title": scraped["title"],
                    "raw_content": scraped["raw_content"],
                    "retrieval_method": SourceRetrievalMethod.URL_PROVIDED.value,
                    "status": SourceStatus.RETRIEVED.value,
                    "retrieved_at": datetime.now(UTC).isoformat(),
                }
            )
            .execute()
            .data[0]
        )

    searched = False
    if not source_rows:
        # No usable explicit sources — fall back to an autonomous web search
        # instead of proceeding ungrounded (EDGE_CASES.md #6 previously
        # treated this as acceptable; a raw_idea alone should still get a
        # chance at real grounding before we give up on sourcing).
        searched = True
        query = f"{request_row['raw_idea']} {request_row['target_audience']}".strip()
        try:
            results = search_web(query, limit=SEARCH_RESULT_LIMIT)
        except SearchFailure as exc:
            failures.append({"url": None, "error": str(exc)})
            results = []
        for result in results:
            source_rows.append(
                db.table("sources")
                .insert(
                    {
                        "content_request_id": request_id,
                        "intake_attachment_id": None,
                        "url": result["url"],
                        "title": result["title"],
                        "raw_content": result["raw_content"],
                        "retrieval_method": SourceRetrievalMethod.WEB_SEARCH.value,
                        "status": SourceStatus.RETRIEVED.value,
                        "retrieved_at": datetime.now(UTC).isoformat(),
                    }
                )
                .execute()
                .data[0]
            )

    usable_count = _select_and_store_sources(db, request_row=request_row, source_rows=source_rows)

    db.table("stage_events").insert(
        {
            "content_request_id": request_id,
            "stage": PipelineStage.RESEARCH.value,
            "status": StageEventStatus.SUCCEEDED.value,
            "detail": {
                "attachments_attempted": len(attachments),
                "sources_retrieved": len(source_rows),
                "sources_usable": usable_count,
                "web_search_used": searched,
                "failures": failures,
            },
        }
    ).execute()

    db.table("content_requests").update(
        {"status": RequestStatus.PLANNING.value, "updated_at": datetime.now(UTC).isoformat()}
    ).eq("id", request_id).execute()

    db.table("jobs").insert(
        {
            "job_type": JobType.PLAN.value,
            "reference_type": JobReferenceType.CONTENT_REQUEST.value,
            "reference_id": request_id,
            "payload": {},
        }
    ).execute()


def _handle_gap_fill_research(job: dict) -> None:
    """Triggered by worker/handlers/evaluate.py when a draft with no
    user-supplied source URL comes back with empty or thin grounding: one
    more web search, this time aimed at what the evaluation actually
    flagged (unsupported claims + feedback), instead of the blind
    idea+audience query the initial pass used. Any usable results are
    marked selected/thin exactly like the initial pass, then a `generate`
    job re-runs against the same draft — worker/handlers/generate.py always
    re-pulls every `selected` source for the request, so new sources found
    here are picked up automatically without any extra wiring."""
    db = get_supabase()
    request_id = job["reference_id"]
    payload = job["payload"]
    draft_id = payload["gap_fill_for_draft_id"]
    research_focus = payload.get("research_focus")

    request_row = db.table("content_requests").select("*").eq("id", request_id).execute().data[0]
    query = f"{request_row['raw_idea']} {request_row['target_audience']} {research_focus or ''}".strip()

    failures = []
    try:
        results = search_web(query, limit=SEARCH_RESULT_LIMIT)
    except SearchFailure as exc:
        failures.append({"url": None, "error": str(exc)})
        results = []

    source_rows = [
        db.table("sources")
        .insert(
            {
                "content_request_id": request_id,
                "intake_attachment_id": None,
                "url": result["url"],
                "title": result["title"],
                "raw_content": result["raw_content"],
                "retrieval_method": SourceRetrievalMethod.WEB_SEARCH.value,
                "status": SourceStatus.RETRIEVED.value,
                "retrieved_at": datetime.now(UTC).isoformat(),
            }
        )
        .execute()
        .data[0]
        for result in results
    ]

    usable_count = _select_and_store_sources(
        db, request_row=request_row, source_rows=source_rows, research_focus=research_focus
    )

    db.table("stage_events").insert(
        {
            "content_request_id": request_id,
            "stage": PipelineStage.RESEARCH.value,
            "status": StageEventStatus.SUCCEEDED.value,
            "detail": {
                "draft_id": draft_id,
                "gap_fill": True,
                "research_focus": research_focus,
                "sources_retrieved": len(source_rows),
                "sources_usable": usable_count,
                "failures": failures,
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
            "payload": {"revision_instructions": payload.get("revision_instructions")},
        }
    ).execute()
