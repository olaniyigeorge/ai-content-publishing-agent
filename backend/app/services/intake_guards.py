"""Deterministic intake validation — catches "too little", "too much", and
"doesn't make sense" content requests before they consume a research/plan/
generate/evaluate pipeline run. Kept dependency-free (no Claude call) so
submission stays instant and these checks stay unit-testable without mocks.
"""

import re

from shared.errors import ValidationFailure

MIN_IDEA_WORDS = 3
MAX_IDEA_LENGTH = 2000

MIN_TARGET_AUDIENCE_LENGTH = 3
MAX_TARGET_AUDIENCE_LENGTH = 300

MAX_SUPPORTING_MATERIAL_CHARS = 5000
MAX_ATTACHMENTS = 10
MAX_ATTACHMENT_DESCRIPTION_LENGTH = 500

_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
_BARE_URL_RE = re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE)


def _word_count(text: str) -> int:
    return len(text.split())


def _looks_like_gibberish(text: str) -> str | None:
    """Cheap, deterministic nonsense heuristics. Not a semantic check (that
    would need a Claude call) — this only catches the mechanically obvious
    cases: no letters at all, a single character hammered repeatedly, or a
    string with no vowels at all (most real phrases have at least one)."""
    letters = re.sub(r"[^a-zA-Z]", "", text)
    if not letters:
        return "contains no actual words"

    stripped = text.replace(" ", "")
    if len(stripped) >= 6 and len(set(stripped.lower())) <= 2:
        return "looks like a repeated/mashed character, not a real idea"

    if len(letters) >= 8 and not re.search(r"[aeiouAEIOU]", letters):
        return "doesn't look like real words (no vowels)"

    return None


def validate_raw_idea(raw_idea: str) -> None:
    idea = raw_idea.strip()
    if len(idea) > MAX_IDEA_LENGTH:
        raise ValidationFailure(f"raw_idea is too long ({len(idea)} chars, max {MAX_IDEA_LENGTH})")
    if _BARE_URL_RE.match(idea):
        raise ValidationFailure("raw_idea is just a URL — add it as a source URL attachment instead")
    gibberish_reason = _looks_like_gibberish(idea)
    if gibberish_reason:
        raise ValidationFailure(f"raw_idea doesn't look like a usable content idea: {gibberish_reason}")
    if _word_count(idea) < MIN_IDEA_WORDS:
        raise ValidationFailure(
            f"raw_idea is too short to be a usable content idea (need at least {MIN_IDEA_WORDS} words)"
        )


def validate_target_audience(target_audience: str) -> None:
    audience = target_audience.strip()
    if len(audience) < MIN_TARGET_AUDIENCE_LENGTH:
        raise ValidationFailure("target_audience is required")
    if len(audience) > MAX_TARGET_AUDIENCE_LENGTH:
        raise ValidationFailure(
            f"target_audience is too long ({len(audience)} chars, max {MAX_TARGET_AUDIENCE_LENGTH})"
        )


def validate_supporting_material(supporting_material: dict | None) -> None:
    if supporting_material is None:
        return
    import json

    serialized = json.dumps(supporting_material)
    if len(serialized) > MAX_SUPPORTING_MATERIAL_CHARS:
        raise ValidationFailure(
            f"supporting_material is too large ({len(serialized)} chars, max {MAX_SUPPORTING_MATERIAL_CHARS})"
        )


def validate_attachments(attachments: list) -> None:
    if len(attachments) > MAX_ATTACHMENTS:
        raise ValidationFailure(f"too many attachments ({len(attachments)}, max {MAX_ATTACHMENTS})")
    for attachment in attachments:
        if attachment.type == "url" and not attachment.url:
            raise ValidationFailure("a 'url' attachment must include a url")
        if attachment.type == "url" and attachment.url and not _URL_RE.match(attachment.url.strip()):
            raise ValidationFailure(f"'{attachment.url}' doesn't look like a valid http(s) URL")
        if attachment.type != "url" and not attachment.storage_path:
            raise ValidationFailure(f"a '{attachment.type}' attachment must include a storage_path")
        if attachment.description and len(attachment.description) > MAX_ATTACHMENT_DESCRIPTION_LENGTH:
            raise ValidationFailure(
                f"attachment description is too long (max {MAX_ATTACHMENT_DESCRIPTION_LENGTH} chars)"
            )
