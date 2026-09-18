"""Structured-output JSON schemas for steps that need a deterministic shape.
These are the guarantee that the evaluation loop and the formatting check are
real, not prose the worker hopes the model followed.
"""

from typing import NoReturn


def require_fields(result: dict, keys: list[str], *, step: str, error_cls: type[Exception]) -> None:
    """Structured-output schemas mark fields `required`, but that's a
    description of intent, not a server-side guarantee (the tool isn't
    declared `strict`) — a rare response can still omit one. Without this,
    that shows up as a bare `KeyError('target_keywords')` in jobs.last_error /
    stage_events — technically "not swallowed" but unreadable to a human
    (TESTING_FINDINGS.md, 2026-09-16). This turns it into a clear, typed
    error instead."""
    missing = [k for k in keys if k not in result]
    if missing:
        _raise_missing_fields(step, missing, result, error_cls)


def _raise_missing_fields(step: str, missing: list[str], result: dict, error_cls: type[Exception]) -> NoReturn:
    raise error_cls(
        f"Claude's {step} response was missing required field(s) {missing} — got: {sorted(result.keys())}"
    )

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
        "target_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Required — never omit this. One primary keyword plus 2-4 secondary keywords "
            "derived from the content idea, per SEO best practice. Omitting this field fails the "
            "planning step outright, even if the outline itself is complete.",
        },
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
                    "unusable_reason": {
                        "type": "string",
                        "description": "Required when usable is false: specifically why (e.g. 'page is a login/paywall "
                        "wall', 'only navigation and footer boilerplate, no article body', 'JS-rendered shell with no "
                        "text in the raw HTML'). Never a generic statement like 'not useful'.",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["strong", "thin"],
                        "description": "Only meaningful when usable is true. 'strong' = clearly authoritative or "
                        "verifiable (primary data, a named study, an official source). 'thin' = real, usable "
                        "evidence that's still weak — a single low-authority blog/opinion piece, outdated "
                        "information, an indirect or unverified claim, or a source only tangentially about the "
                        "topic. Do not mark a source unusable just because it's thin — thin evidence should still "
                        "be cited, honestly labeled, not hidden or dressed up as solid.",
                    },
                    "confidence_reason": {
                        "type": "string",
                        "description": "Required when confidence is 'thin': the specific reason it's weak (e.g. "
                        "'single personal blog post, no data or citations', 'article is from 2019, likely outdated "
                        "for this topic', 'source only mentions this in passing'). Never a generic statement.",
                    },
                },
                "required": ["source_id", "excerpt_selected", "relevance_notes", "usable", "confidence"],
            },
        }
    },
    "required": ["sources"],
}

# evidence-driven regeneration (worker/handlers/gather_evidence.py): given one
# specific claim and one candidate source's raw retrieved content, decide
# whether that source actually supports the claim — never whether a URL
# merely exists. `excerpt` is checked against the source's real content by
# claude/grounding_validator.py's caller before it's trusted; this schema
# only constrains the model's *response* shape, not whether it told the
# truth about the excerpt being verbatim.
CLAIM_VERIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "supports_claim": {
            "type": "boolean",
            "description": "True only if this source directly backs the claim — not just related to the topic.",
        },
        "excerpt": {
            "type": "string",
            "description": "A short passage copied verbatim from the source content that supports the claim. "
            "Empty string if supports_claim is false. Never paraphrase — copy exactly.",
        },
        "reason": {"type": "string"},
    },
    "required": ["supports_claim", "excerpt", "reason"],
}

INTAKE_PLAUSIBILITY_SCHEMA = {
    "type": "object",
    "properties": {
        "plausible": {
            "type": "boolean",
            "description": "True if this is a real, coherent content idea and target audience that a "
            "content team could actually research and write about. False for gibberish, keyboard-mashed "
            "text, or text with no discernible topic.",
        },
        "reason": {
            "type": "string",
            "description": "One short sentence. If plausible, why (what the actual topic/audience is). "
            "If not, what specifically makes it unusable — never a generic 'not useful'.",
        },
    },
    "required": ["plausible", "reason"],
}
