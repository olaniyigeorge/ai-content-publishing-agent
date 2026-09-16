from datetime import UTC, datetime

import claude.service as claude_service
from claude.outputs import require_fields
from db.client import get_supabase
from shared.enums import (
    JobReferenceType,
    JobType,
    PipelineStage,
    RequestStatus,
    SourceRetrievalMethod,
    SourceStatus,
    StageEventStatus,
)
from shared.errors import ResearchFailure
from worker.firecrawl import ScrapeFailure, scrape_url


def handle_research(job: dict) -> None:
    """EDGE_CASES.md #6: if every source fails to retrieve, this must be
    visible — the pipeline still proceeds (a raw_idea alone is a valid
    request per scenario 1) but stage_events records zero usable sources so
    a human/reviewer can see the gap, not just an article with no grounding.
    """
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

    if source_rows:
        selection = claude_service.select_sources(
            raw_idea=request_row["raw_idea"],
            target_audience=request_row["target_audience"],
            sources=source_rows,
        )
        require_fields(selection, ["sources"], step="source selection", error_cls=ResearchFailure)
        by_id = {s["source_id"]: s for s in selection["sources"] if "source_id" in s}
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
            db.table("sources").update(
                {
                    "excerpt_selected": picked.get("excerpt_selected"),
                    "relevance_notes": picked.get("relevance_notes"),
                    "status": SourceStatus.SELECTED.value,
                }
            ).eq("id", row["id"]).execute()

    usable_count = sum(1 for r in source_rows if by_id.get(r["id"], {}).get("usable")) if source_rows else 0

    db.table("stage_events").insert(
        {
            "content_request_id": request_id,
            "stage": PipelineStage.RESEARCH.value,
            "status": StageEventStatus.SUCCEEDED.value,
            "detail": {
                "attachments_attempted": len(attachments),
                "sources_retrieved": len(source_rows),
                "sources_usable": usable_count,
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
