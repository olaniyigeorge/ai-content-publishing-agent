SYSTEM = """You are a content strategist. Given a content idea, target \
audience, and a set of selected source excerpts, produce an article outline. \

Rules:
- Every section must map to at least one source_id, unless the section is \
  purely structural (e.g. an intro/conclusion with no factual claim).
- Derive target_keywords from the content idea: one primary keyword plus 2-4 \
  relevant secondary keywords, per SEO best practice (primary keyword must be \
  usable in the title and first 100 words of the eventual article).
- Let the depth of each section reflect how much source material actually \
  supports it — don't plan a deep section on a topic with thin sourcing."""


def build_user_message(*, raw_idea: str | None, target_audience: str, sources: list[dict]) -> str:
    source_blocks = "\n".join(
        f"- source_id: {s['id']} | excerpt: {s['excerpt_selected']} | notes: {s['relevance_notes']}"
        for s in sources
    )
    return (
        f"Content idea: {raw_idea or '(none provided — infer a reasonable angle from the sources)'}\n"
        f"Target audience: {target_audience}\n\n"
        f"Selected sources:\n{source_blocks}"
    )
