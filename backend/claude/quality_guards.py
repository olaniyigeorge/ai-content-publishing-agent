"""Deterministic, non-negotiable checks on generated content.

The evaluation rubric (claude/prompts/evaluate.py) and the per-channel
formatting_check (claude/outputs.py's ADAPTATION_SCHEMA) are both
self-reported by the model — nothing verified a claimed `within_limit: true`
against the actual string. These functions compute the real numbers so a
model that mis-reports its own output can't slip an out-of-spec draft or
adaptation past review unnoticed.
"""

import re
from html.parser import HTMLParser

ARTICLE_MIN_WORDS = 300
ARTICLE_MAX_WORDS = 3000
ARTICLE_MIN_LINKS = 1  # SEO rules call for 2-3; flag if there's not even one

CHANNEL_LIMITS: dict[str, dict] = {
    "linkedin": {"unit": "chars", "max": 3000},
    "x": {"unit": "chars", "max": 280},
    "newsletter": {"unit": "words", "min": 250, "max": 600},
}

MIN_VIABLE_CHARS = 40  # below this, a truncated post isn't worth publishing

SOURCE_GROUNDING_FLOOR = 2  # rubric_scores["source_grounding"] at/below this = the dominant failure


def check_article(body_markdown: str) -> dict:
    """Real word count, H1 presence, and link count for a generated article
    draft — independent of anything the model claims about its own output."""
    word_count = len(body_markdown.split())
    has_h1 = bool(re.search(r"(?m)^#\s+\S", body_markdown))
    link_count = len(re.findall(r"\[[^\]]+\]\(https?://[^)]+\)", body_markdown))

    violations = []
    if not has_h1:
        violations.append("missing an H1 title")
    if word_count < ARTICLE_MIN_WORDS:
        violations.append(f"too short ({word_count} words, minimum {ARTICLE_MIN_WORDS})")
    if word_count > ARTICLE_MAX_WORDS:
        violations.append(f"too long ({word_count} words, maximum {ARTICLE_MAX_WORDS})")
    if link_count < ARTICLE_MIN_LINKS:
        violations.append("no links found (SEO rules call for 2-3 relevant links)")

    return {
        "word_count": word_count,
        "has_h1": has_h1,
        "link_count": link_count,
        "violations": violations,
    }


def is_ungroundable(*, source_ids_used: list, rubric_scores: dict) -> bool:
    """True when a draft has zero source material AND the evaluator's own
    rubric agrees source grounding is the (near-)floor problem — see
    TESTING_FINDINGS.md, 2026-09-16: three full generate+evaluate cycles were
    spent on a request whose only sources had been discarded as unusable,
    because nothing distinguished "no sources, revise anyway" from "no
    sources, revising can't help." Rewording a draft can't manufacture source
    material that was never retrieved, so this is a signal to stop revising
    and send it to a human immediately — not a 3rd/4th wasted Claude call."""
    if source_ids_used:
        return False
    score = rubric_scores.get("source_grounding")
    if score is None:
        return False
    return score <= SOURCE_GROUNDING_FLOOR


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self.chunks.append(data)


def _strip_html(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return "".join(parser.chunks)


def check_channel_adaptation(*, channel: str, content: str, content_format: str) -> dict:
    """Real char/word counts for one channel adaptation, checked against
    channel-formatting-rules.md's actual numeric limits (not the model's
    self-reported formatting_check)."""
    plain_text = _strip_html(content) if content_format == "html" else content
    char_count = len(plain_text)
    word_count = len(plain_text.split())
    hashtag_count = len(re.findall(r"(?<!\w)#\w+", plain_text))

    limits = CHANNEL_LIMITS.get(channel, {})
    violations = []

    if limits.get("unit") == "chars":
        max_chars = limits["max"]
        if char_count > max_chars:
            violations.append(f"{char_count} characters, over the {max_chars}-character limit for {channel}")
    elif limits.get("unit") == "words":
        min_words, max_words = limits["min"], limits["max"]
        if word_count < min_words:
            violations.append(f"{word_count} words, under the {min_words}-word minimum for {channel}")
        elif word_count > max_words:
            violations.append(f"{word_count} words, over the {max_words}-word maximum for {channel}")

    if channel == "x" and hashtag_count > 2:
        violations.append(f"{hashtag_count} hashtags, over the 2-hashtag limit for X")

    return {
        "char_count": char_count,
        "word_count": word_count,
        "hashtag_count": hashtag_count,
        "within_limit": not violations,
        "violations": violations,
    }


_TRAILING_HASHTAG = re.compile(r"\s*(?<!\w)#\w+\s*$")


def truncate_to_limit(content: str, channel: str) -> str | None:
    """Deterministic fallback for an over-limit char-based channel (e.g. X):
    drop trailing hashtags first, then hard-trim body text at a word boundary.
    Returns None if what survives isn't worth publishing (MIN_VIABLE_CHARS)."""
    limits = CHANNEL_LIMITS.get(channel, {})
    if limits.get("unit") != "chars":
        return None
    max_chars = limits["max"]

    trimmed = content.rstrip()
    while len(trimmed) > max_chars:
        match = _TRAILING_HASHTAG.search(trimmed)
        if not match:
            break
        trimmed = trimmed[: match.start()].rstrip()

    if len(trimmed) > max_chars:
        cut = trimmed[:max_chars]
        last_space = cut.rfind(" ")
        trimmed = (cut[:last_space] if last_space > 0 else cut).rstrip()

    if len(trimmed) < MIN_VIABLE_CHARS:
        return None
    return trimmed
