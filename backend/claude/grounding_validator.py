"""Pre-flight grounding validator — a cheap, deterministic gate that runs on
every freshly generated draft in worker/handlers/generate.py, before the
expensive per-draft evaluator call. It doesn't replace the evaluator's
judgment (tone, structure, argument quality); it only mechanically catches
the failure modes that don't need judgment to detect: a citation pointing at
a URL that was never actually provided, a claim stated as settled fact with
no citation nearby, a stat that doesn't match what its own cited source
excerpt actually says.

This is the enforcement layer the objective calls for: the system must
mechanically require grounding, not just hope the model followed the
evaluator's prior feedback.
"""

import re

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_NUMBER = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?\b")
_WORD = re.compile(r"[a-z']+")
_PROPER_NOUN = re.compile(r"\b[A-Z][a-zA-Z]+(?:['’][a-z]+)?\b")

# Words that are capitalized for reasons unrelated to naming a publisher/
# report (generic descriptors, sentence-position artifacts) — excluded so
# the attribution check only fires on actual proper nouns.
_ATTRIBUTION_STOPWORDS = {
    "The", "A", "An", "This", "That", "It", "In", "On", "For", "With", "By", "According",
    "Report", "Study", "Research", "Survey", "Data", "Source", "Sources", "And", "Or", "Its",
}

TREND_PHRASES = [
    r"\bincreasingly\b",
    r"\bgrowing trend\b",
    r"\bon the rise\b",
    r"\bmore and more\b",
    r"\bis becoming (?:more|less) common\b",
    r"\ba (?:growing|rising) number of\b",
    r"\btrend(?:ing)? (?:toward|towards)\b",
    r"\bmore agencies (?:are|have been)\b",
]

CAUSAL_PHRASES = [
    r"\bcauses?\b",
    r"\bleads? to\b",
    r"\bresults? in\b",
    r"\bdue to\b",
    r"\bbecause of\b",
    r"\bdrives?\b",
    r"\bis (?:the reason|why)\b",
]

ASSERTION_PHRASES = [
    r"\bstudies show\b",
    r"\bresearch (?:shows|indicates|suggests)\b",
    r"\bdata shows\b",
    r"\baccording to (?:a study|research|reports?)\b",
    r"\bexperts? (?:agree|say)\b",
    r"\bmost (?:agencies|companies|businesses|marketers)\b",
]

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with", "is", "are", "was",
    "were", "this", "that", "it", "as", "by", "at", "from", "be", "has", "have", "its", "their",
    "which", "who", "what", "not", "than", "into", "about", "your", "you", "will", "can", "more",
}


def _sentences(body_markdown: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(body_markdown) if s.strip()]


def _has_citation(sentence: str) -> bool:
    return bool(_MARKDOWN_LINK.search(sentence))


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _strip_link_urls(text: str) -> str:
    """Keeps a markdown link's visible anchor text but drops the URL itself
    — otherwise words baked into a URL slug (e.g. ".../agency-retainer-report")
    pollute the word-overlap check below with terms the sentence never
    actually said."""
    return _MARKDOWN_LINK.sub(lambda m: m.group(1), text)


def _significant_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(_strip_link_urls(text).lower()) if w not in _STOPWORDS and len(w) > 3}


def _attribution_terms(anchor: str) -> set[str]:
    """Proper-noun-looking words in a citation's visible link text — the
    words a reader would read as naming *who published this* (e.g. "Adobe"
    in "Adobe's 2026 marketing report"). Used to catch fabricated publisher
    attribution, which citation_mismatch's any-word-overlap check misses:
    a sentence like "According to [Adobe's 2026 marketing report](url), 8 in
    10 marketing teams..." shares plenty of real words ("marketing",
    "teams") with a genuinely relevant excerpt, so citation_mismatch passes
    it — even when "Adobe" and "2026" were invented wholesale for a source
    excerpt that carries no publisher, title, or date at all (evaluator
    finding on request fa6c3e72, 2026-09-18)."""
    return {w for w in _PROPER_NOUN.findall(anchor) if w not in _ATTRIBUTION_STOPWORDS and len(w) > 2}


def validate_grounding(*, body_markdown: str, sources: list[dict]) -> dict:
    """`sources` is the same list[dict] shape passed to generate_draft (each
    needs `url`; `excerpt_selected` powers the citation-mismatch and
    quantitative-drift checks). Returns
    {"passed": bool, "violations": list[str]}.

    A source can be marked `selected` (request_state_service.override_source_status)
    even when it was never actually fetched — e.g. a reviewer clicking "mark
    selected" on a failed/blocked source, or asking the model to "try again"
    on a URL that 403'd. That source has no `excerpt_selected` to check
    anything against. Treating its URL as "known" anyway would let a
    citation to it skip every check below (fabricated_url passes because the
    URL is "known"; citation_mismatch and quantitative_paraphrase_drift both
    no-op on an empty excerpt) — a free pass to attribute any claim to a
    source with zero actual content behind it (TESTING_FINDINGS2.md,
    2026-09-18). Only URLs with real retrieved content count as known."""
    known_urls = {s["url"] for s in sources if s.get("url") and s.get("excerpt_selected")}
    excerpt_by_url = {s["url"]: s["excerpt_selected"] for s in sources if s.get("url") and s.get("excerpt_selected")}
    title_by_url = {s["url"]: (s.get("title") or "") for s in sources if s.get("url")}
    violations: list[str] = []

    # 1. fabricated/unverified URLs — cited but never actually provided.
    for _anchor, url in _MARKDOWN_LINK.findall(body_markdown):
        if url not in known_urls:
            violations.append(f"fabricated_url: draft cites {url}, which was never provided as a source")

    sentences = _sentences(body_markdown)
    for sentence in sentences:
        cited = _has_citation(sentence)

        # 2/3. unsupported trend / causal claims — assertion patterns with no citation in the same sentence.
        if not cited and _matches_any(TREND_PHRASES, sentence):
            violations.append(f'unsupported_trend_claim: "{sentence[:160]}"')
        if not cited and _matches_any(CAUSAL_PHRASES, sentence):
            violations.append(f'unsupported_causal_claim: "{sentence[:160]}"')
        # 4. unsupported claims generally (data/research/expert assertions with no citation).
        if not cited and _matches_any(ASSERTION_PHRASES, sentence):
            violations.append(f'unsupported_claim: "{sentence[:160]}"')

        # 5/6/7. citation mismatch + quantitative paraphrase drift + fabricated
        # attribution — only checkable when the sentence cites a known source
        # whose excerpt we have.
        for anchor, url in _MARKDOWN_LINK.findall(sentence):
            excerpt = excerpt_by_url.get(url)
            if not excerpt:
                continue

            # 7. fabricated attribution — a proper noun in the citation's
            # visible text (a claimed publisher/report name) that appears
            # neither in the source's recorded title nor in its retrieved
            # excerpt. Catches invented publishers/report names even when
            # the surrounding sentence otherwise overlaps enough with the
            # excerpt to pass citation_mismatch, and even when the claim
            # carries no number for quantitative_paraphrase_drift to catch.
            real_title_words = {w.lower() for w in _PROPER_NOUN.findall(title_by_url.get(url, ""))}
            excerpt_lower = excerpt.lower()
            for term in _attribution_terms(anchor):
                if term.lower() not in real_title_words and term.lower() not in excerpt_lower:
                    violations.append(
                        f'fabricated_attribution: citation text "{anchor}" names "{term}" for {url}, but '
                        f"neither that source's recorded title nor its retrieved excerpt confirms it"
                    )
            sentence_words = _significant_words(sentence)
            excerpt_words = _significant_words(excerpt)
            if sentence_words and not (sentence_words & excerpt_words):
                violations.append(
                    f'citation_mismatch: sentence citing {url} shares no relevant terms with that '
                    f'source\'s excerpt: "{sentence[:160]}"'
                )
            # The URL itself often contains digits (an article ID, a slug
            # like ".../158957-resource-poor-risk-rich...") that have
            # nothing to do with any number the sentence actually states.
            # Extracting numbers from the raw sentence (URL included) was
            # flagging that digit as a "stated" figure never found in the
            # excerpt — a false positive on every single draft citing that
            # URL, no matter how the prose was reworded (seen recurring
            # identically across v1-v3 of a real request, 2026-09-17).
            # Strip the URL out first, exactly as citation-mismatch already
            # does via _significant_words, so only prose numbers count.
            sentence_numbers = set(_NUMBER.findall(_strip_link_urls(sentence)))
            excerpt_numbers = set(_NUMBER.findall(excerpt))
            drifted = sentence_numbers - excerpt_numbers
            if drifted:
                violations.append(
                    f"quantitative_paraphrase_drift: draft states {sorted(drifted)} attributed to {url}, "
                    f"but its cited excerpt doesn't contain that figure"
                )

    return {"passed": not violations, "violations": violations}
