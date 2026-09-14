"""Structured-output JSON schemas for steps that need a deterministic shape.
These are the guarantee that the evaluation loop and the formatting check are
real, not prose the worker hopes the model followed.
"""

RUBRIC_CRITERIA = [
    "topic_relevance",
    "source_grounding",
    "factual_consistency",
    "audience_fit",
    "tone",
    "seo_fit",
    "channel_fit",
    "clarity",
    "completeness",
]

# content-evaluation-rubric.md: overall status pass/revise/reject, scores or
# notes per criterion, unsupported/weak claims, sections needing revision,
# specific recommended changes, final approval status.
EVALUATION_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_status": {
            "type": "string",
            "enum": ["pass", "revise", "reject"],
        },
        "rubric_scores": {
            "type": "object",
            "properties": {c: {"type": "integer", "minimum": 1, "maximum": 5} for c in RUBRIC_CRITERIA},
            "required": RUBRIC_CRITERIA,
        },
        "overall_score": {"type": "number"},
        "unsupported_claims": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Claims in the draft that are not backed by any provided source excerpt.",
        },
        "sections_to_revise": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recommended_changes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific, actionable instructions for the next draft revision — not generic feedback.",
        },
        "feedback": {"type": "string"},
    },
    "required": [
        "overall_status",
        "rubric_scores",
        "overall_score",
        "unsupported_claims",
        "sections_to_revise",
        "recommended_changes",
        "feedback",
    ],
}

# channel-formatting-rules.md: one schema per channel's adapted output plus
# the formatting-check metadata the human reviewer sees before approval.
ADAPTATION_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
        "content_format": {"type": "string", "enum": ["plain_text", "html"]},
        "formatting_check": {
            "type": "object",
            "description": "Channel-specific metadata: char_count/within_limit for linkedin+x, "
            "hashtag_count for x, subject_line/word_count for newsletter, etc.",
        },
    },
    "required": ["content", "content_format", "formatting_check"],
}

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "outline": {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": {"type": "string"},
                            "source_ids": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["heading", "source_ids"],
                    },
                }
            },
            "required": ["sections"],
        },
        "target_keywords": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["outline", "target_keywords"],
}

# research/source-selection: per source, which excerpt matters and why —
# this is what powers "make it clear which sources informed the output".
SOURCE_SELECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "excerpt_selected": {"type": "string"},
                    "relevance_notes": {
                        "type": "string",
                        "description": "Specific reason this excerpt matters — not a generic statement.",
                    },
                    "usable": {
                        "type": "boolean",
                        "description": "False if the retrieved content had no usable article text (nav/ads/JS shell).",
                    },
                },
                "required": ["source_id", "excerpt_selected", "relevance_notes", "usable"],
            },
        }
    },
    "required": ["sources"],
}
