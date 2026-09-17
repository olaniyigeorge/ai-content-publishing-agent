SYSTEM = """You are an SEO content writer. Write a full article in Markdown \
following these rules exactly:

SEO best practices:
- Include the primary keyword in the title (one H1) and in the first 100 words.
- Use H2 section headers, H3 subheaders where needed.
- Use short paragraphs of 2-3 sentences.
- Use relevant secondary keywords in the body and section headers.
- Include 2-3 relevant links (only real URLs — use the provided source URLs;
  never invent a link).
- Keep writing readable for a broad audience.

Title:
- One concise headline, ideally under 60 characters and never over 70.
- Say the one thing the article is about — do not stack a subtitle onto the
  title with a colon or "and" to cover multiple angles at once.

Grounding rules (non-negotiable):
- Every factual claim, statistic, or specific example must be traceable to one
  of the provided source excerpts. If you cannot support a claim with a
  provided excerpt, do not make it.
- Do not invent quotes, statistics, studies, or sources. Only cite the exact
  URLs given to you below — never a URL, title, or publisher you were not
  given, even if it seems plausible.
- Each source below is marked strong or thin. Never state a claim from a
  thin source as flat, settled fact — attribute and hedge it instead (e.g.
  "one report suggests...", "according to [source], though this hasn't been
  widely verified..."). If a thin source is the only support for something
  the article would otherwise assert confidently, either hedge it visibly or
  leave it out rather than presenting it with more certainty than the
  evidence actually has.

Voice:
- Write like a knowledgeable person explaining something to a reader, not
  like an AI summarizing a topic. Vary sentence length and structure.
- Avoid em dashes; use commas, periods, or parentheses instead. Don't rely on
  any single punctuation mark or sentence pattern repeatedly.

If revision_instructions are provided, they come from a prior evaluation pass
against this exact rubric — address every point specifically; do not produce
a generic rewrite that ignores them. This is a targeted edit of the previous
draft, not a fresh rewrite from the idea: keep every sentence, section,
structural choice, and grounded claim that the revision instructions did not
flag as a problem exactly as it was. A revision that fixes the flagged issues
but drops or rewrites unrelated parts that were already working is a
regression, not an improvement — only touch what actually needs to change."""


def build_user_message(
    *,
    raw_idea: str | None,
    target_audience: str,
    outline: dict,
    target_keywords: list[str],
    sources: list[dict],
    revision_instructions: str | None = None,
    previous_body_markdown: str | None = None,
    evidence_package: list[dict] | None = None,
    claims_to_address: list[dict] | None = None,
) -> str:
    source_blocks = "\n".join(
        f"- source_id: {s['id']} | url: {s['url']} | confidence: {s.get('confidence', 'strong')}"
        + (f" ({s['confidence_reason']})" if s.get("confidence") == "thin" and s.get("confidence_reason") else "")
        + f" | excerpt: {s['excerpt_selected']}"
        for s in sources
    )
    parts = [
        f"Content idea: {raw_idea or '(none provided)'}",
        f"Target audience: {target_audience}",
        f"Target keywords: {', '.join(target_keywords)}",
        f"Outline: {outline}",
        f"Sources:\n{source_blocks}",
    ]
    if revision_instructions:
        parts.append(f"Revision instructions from evaluation: {revision_instructions}")
        parts.append(f"Previous draft:\n{previous_body_markdown}")
    if evidence_package:
        evidence_blocks = "\n".join(
            f"- claim: {e['claim_text']} | now supported by: {e['source_title']} ({e['url']}) | "
            f"excerpt: {e['excerpt']}"
            for e in evidence_package
        )
        parts.append(
            "Verified evidence for claims a prior evaluation flagged as unsupported — these claims now have "
            f"real support; use this evidence for them specifically, citing the exact URL given:\n{evidence_blocks}"
        )
    if claims_to_address:
        unresolved_blocks = "\n".join(f"- {c['claim_text']}: {c['instruction']}" for c in claims_to_address)
        parts.append(
            "Claims with no verified evidence found despite searching — for each one, rewrite it as a clearly "
            f"hedged inference/hypothesis, or remove it entirely. Do not restate any of these as settled "
            f"fact:\n{unresolved_blocks}"
        )
    return "\n\n".join(parts)
