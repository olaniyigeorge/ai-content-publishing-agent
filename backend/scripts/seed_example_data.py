"""Inserts the example request trace from architecture.md §8 through every
table — auth rows, intake, research, plan, two draft versions (showing the
revision lineage), evaluations, human review, three channel adaptations, and
a publishing_queue with one published, one scheduled, one dead-lettered item.

This is what makes the Loom video reproducible: seed, then run
`python -m scripts.print_stage_events <content_request_id>` (or hit the
request's detail endpoint) to show the same story every time.

Usage: python -m scripts.seed_example_data
"""

from db.client import get_supabase

USER_ID = "10000000-0000-0000-0000-000000000001"
REQUEST_ID = "20000000-0000-0000-0000-000000000001"
ATTACHMENT_1 = "30000000-0000-0000-0000-000000000001"
ATTACHMENT_2 = "30000000-0000-0000-0000-000000000002"
ATTACHMENT_3 = "30000000-0000-0000-0000-000000000003"
SOURCE_1 = "40000000-0000-0000-0000-000000000001"
SOURCE_2 = "40000000-0000-0000-0000-000000000002"
PLAN_ID = "50000000-0000-0000-0000-000000000001"
DRAFT_V1 = "60000000-0000-0000-0000-000000000001"
DRAFT_V2 = "60000000-0000-0000-0000-000000000002"
EVAL_1 = "70000000-0000-0000-0000-000000000001"
EVAL_2 = "70000000-0000-0000-0000-000000000002"
REVIEW_ID = "80000000-0000-0000-0000-000000000001"
ADAPT_LINKEDIN = "90000000-0000-0000-0000-000000000001"
ADAPT_X = "90000000-0000-0000-0000-000000000002"
ADAPT_NEWSLETTER = "90000000-0000-0000-0000-000000000003"
QUEUE_LINKEDIN = "a0000000-0000-0000-0000-000000000001"
QUEUE_X = "a0000000-0000-0000-0000-000000000002"
QUEUE_NEWSLETTER = "a0000000-0000-0000-0000-000000000003"


def main() -> None:
    db = get_supabase()

    db.table("access_rules").upsert(
        {"id": "00000000-0000-0000-0000-000000000001", "type": "domain", "value": "koyatalent.com"}
    ).execute()

    db.table("users").upsert({"id": USER_ID, "email": "amaka@koyatalent.com"}).execute()

    db.table("content_requests").upsert(
        {
            "id": REQUEST_ID,
            "raw_idea": "5 productivity tips for remote SaaS teams, backed by recent research",
            "target_audience": "B2B SaaS marketing managers, mid-career, US-based",
            "supporting_material": {"notes": "Tie in the Gartner hybrid-work stat if possible"},
            "status": "published",
            "submitted_by_user_id": USER_ID,
        }
    ).execute()

    db.table("intake_attachments").upsert(
        [
            {
                "id": ATTACHMENT_1,
                "content_request_id": REQUEST_ID,
                "type": "url",
                "url": "https://hbr.org/2026/06/remote-team-productivity-study",
            },
            {
                "id": ATTACHMENT_2,
                "content_request_id": REQUEST_ID,
                "type": "url",
                "url": "https://gartner.com/reports/hybrid-work-2026",
            },
            {
                "id": ATTACHMENT_3,
                "content_request_id": REQUEST_ID,
                "type": "image",
                "storage_path": f"intake-media/{REQUEST_ID}/chart.png",
                "description": "Screenshot of Gartner hybrid-work adoption chart",
            },
        ]
    ).execute()

    db.table("sources").upsert(
        [
            {
                "id": SOURCE_1,
                "content_request_id": REQUEST_ID,
                "intake_attachment_id": ATTACHMENT_1,
                "url": "https://hbr.org/2026/06/remote-team-productivity-study",
                "title": "The Remote Team Productivity Study",
                "raw_content": "<full scraped article text>",
                "excerpt_selected": "Teams with structured async check-ins reported 23% higher self-rated productivity.",
                "relevance_notes": "Primary statistic for the article's core claim about async check-ins.",
                "retrieval_method": "url_provided",
                "status": "selected",
            },
            {
                "id": SOURCE_2,
                "content_request_id": REQUEST_ID,
                "intake_attachment_id": ATTACHMENT_2,
                "url": "https://gartner.com/reports/hybrid-work-2026",
                "title": "Hybrid Work Adoption 2026",
                "raw_content": "<full scraped report text>",
                "excerpt_selected": "68% of B2B SaaS companies adopted a hybrid-first policy as of Q2 2026.",
                "relevance_notes": "Supports audience-relevance framing — the request is specifically about SaaS teams.",
                "retrieval_method": "url_provided",
                "status": "selected",
            },
        ]
    ).execute()

    db.table("content_plans").upsert(
        {
            "id": PLAN_ID,
            "content_request_id": REQUEST_ID,
            "outline": {
                "sections": [
                    {"heading": "Why remote productivity is a SaaS-specific problem", "source_ids": [SOURCE_2]},
                    {"heading": "Tip 1: Structured async check-ins", "source_ids": [SOURCE_1]},
                ]
            },
            "target_keywords": ["remote team productivity", "hybrid work SaaS", "async check-ins"],
        }
    ).execute()

    db.table("article_drafts").upsert(
        [
            {
                "id": DRAFT_V1,
                "content_request_id": REQUEST_ID,
                "content_plan_id": PLAN_ID,
                "option_label": "A",
                "version": 1,
                "parent_draft_id": None,
                "title": "5 Productivity Tips for Remote SaaS Teams, Backed by 2026 Research",
                "body_markdown": "## Why remote productivity is a SaaS-specific problem\n\n...",
                "source_ids_used": [SOURCE_1, SOURCE_2],
                "status": "discarded",
            },
            {
                "id": DRAFT_V2,
                "content_request_id": REQUEST_ID,
                "content_plan_id": PLAN_ID,
                "option_label": "A",
                "version": 2,
                "parent_draft_id": DRAFT_V1,
                "title": "5 Productivity Tips for Remote SaaS Teams, Backed by 2026 Research",
                "body_markdown": "## Why remote productivity is a SaaS-specific problem\n\n<tighter, stat-led rewrite>...",
                "source_ids_used": [SOURCE_1, SOURCE_2],
                "status": "selected",
            },
        ]
    ).execute()

    db.table("evaluations").upsert(
        [
            {
                "id": EVAL_1,
                "article_draft_id": DRAFT_V1,
                "rubric_scores": {"accuracy": 4, "clarity": 3, "seo": 4, "tone_fit": 3},
                "overall_score": 3.5,
                "passed_threshold": False,
                "feedback": "Intro is generic and doesn't lead with the Gartner stat; tone slightly too casual.",
                "revision_instructions": "Open with the 68% hybrid-adoption stat; tighten tone for the audience.",
                "evaluated_by": "ai",
            },
            {
                "id": EVAL_2,
                "article_draft_id": DRAFT_V2,
                "rubric_scores": {"accuracy": 4, "clarity": 5, "seo": 4, "tone_fit": 5},
                "overall_score": 4.5,
                "passed_threshold": True,
                "feedback": "Strong open, tone matches audience, every claim traces to a source.",
                "revision_instructions": None,
                "evaluated_by": "ai",
            },
        ]
    ).execute()

    db.table("human_reviews").upsert(
        {
            "id": REVIEW_ID,
            "content_request_id": REQUEST_ID,
            "article_draft_id": DRAFT_V2,
            "reviewer_user_id": USER_ID,
            "decision": "approved",
            "notes": "Good to go, ship as-is.",
        }
    ).execute()

    db.table("channel_adaptations").upsert(
        [
            {
                "id": ADAPT_LINKEDIN,
                "content_request_id": REQUEST_ID,
                "article_draft_id": DRAFT_V2,
                "channel": "linkedin",
                "content": "Remote SaaS teams are 23% more productive with one simple change: structured async check-ins.",
                "content_format": "plain_text",
                "formatting_check": {"char_count": 267, "within_limit": True},
                "status": "published",
            },
            {
                "id": ADAPT_X,
                "content_request_id": REQUEST_ID,
                "article_draft_id": DRAFT_V2,
                "channel": "x",
                "content": "68% of B2B SaaS companies went hybrid-first in 2026. The teams that stayed productive: async check-ins.",
                "content_format": "plain_text",
                "formatting_check": {"char_count": 141, "within_limit": True},
                "status": "approved",
            },
            {
                "id": ADAPT_NEWSLETTER,
                "content_request_id": REQUEST_ID,
                "article_draft_id": DRAFT_V2,
                "channel": "newsletter",
                "content": "<h2>5 Productivity Tips for Remote SaaS Teams</h2><p>New 2026 research shows...</p>",
                "content_format": "html",
                "formatting_check": {"subject_line_length": 42, "within_limit": True},
                "status": "approved",
            },
        ]
    ).execute()

    db.table("publishing_queue").upsert(
        [
            {
                "id": QUEUE_LINKEDIN,
                "channel_adaptation_id": ADAPT_LINKEDIN,
                "status": "published",
                "attempts": 1,
                "published_at": "2026-09-10T09:30:05Z",
            },
            {
                "id": QUEUE_X,
                "channel_adaptation_id": ADAPT_X,
                "scheduled_for": "2026-09-11T14:00:00Z",
                "status": "queued",
                "attempts": 0,
                "next_attempt_at": "2026-09-11T14:00:00Z",
            },
            {
                "id": QUEUE_NEWSLETTER,
                "channel_adaptation_id": ADAPT_NEWSLETTER,
                "status": "dead_letter",
                "attempts": 3,
                "last_error": "Mailgun API 502: upstream timeout",
            },
        ]
    ).execute()

    db.table("stage_events").insert(
        [
            {"content_request_id": REQUEST_ID, "stage": "intake", "status": "succeeded", "detail": {"attachments": 3}},
            {"content_request_id": REQUEST_ID, "stage": "research", "status": "succeeded", "detail": {"sources_retrieved": 2}},
            {"content_request_id": REQUEST_ID, "stage": "generation", "status": "succeeded", "detail": {"draft_id": DRAFT_V1, "version": 1}},
            {"content_request_id": REQUEST_ID, "stage": "evaluation", "status": "succeeded", "detail": {"draft_id": DRAFT_V1, "passed_threshold": False}},
            {"content_request_id": REQUEST_ID, "stage": "revision", "status": "succeeded", "detail": {"draft_id": DRAFT_V2, "version": 2}},
            {"content_request_id": REQUEST_ID, "stage": "human_review", "status": "succeeded", "detail": {"decision": "approved"}},
            {
                "content_request_id": REQUEST_ID,
                "stage": "publishing",
                "status": "failed",
                "detail": {"channel_adaptation_id": ADAPT_NEWSLETTER, "attempt": 3},
                "error_message": "Mailgun API 502: upstream timeout",
            },
        ]
    ).execute()

    print(f"seeded content_request {REQUEST_ID}")
    print(f"run: python -m scripts.print_stage_events {REQUEST_ID}")


if __name__ == "__main__":
    main()
