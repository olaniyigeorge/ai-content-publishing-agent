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

Grounding rules (non-negotiable):
- Every factual claim, statistic, or specific example must be traceable to one
  of the provided source excerpts. If you cannot support a claim with a
  provided excerpt, do not make it.
- Do not invent quotes, statistics, studies, or sources.

If revision_instructions are provided, they come from a prior evaluation pass
against this exact rubric — address every point specifically; do not produce
a generic rewrite that ignores them."""


def build_user_message(
    *,
    raw_idea: str | None,
    target_audience: str,
    outline: dict,
    target_keywords: list[str],
    sources: list[dict],
    revision_instructions: str | None = None,
    previous_body_markdown: str | None = None,
) -> str:
    source_blocks = "\n".join(
        f"- source_id: {s['id']} | url: {s['url']} | excerpt: {s['excerpt_selected']}" for s in sources
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
    return "\n\n".join(parts)
