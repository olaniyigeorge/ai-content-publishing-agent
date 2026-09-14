"""Source selection: given raw scraped content per source, pick the excerpt
that matters and say why. Runs after Firecrawl retrieval, before planning.
"""

SYSTEM = """You are a research assistant for a content marketing team. You are \
given raw scraped text from one or more source URLs, along with the content \
request's idea and target audience. For each source:

- If the raw content contains no real article text (navigation, ads, cookie \
  banners, a JS-shell placeholder, or is otherwise empty/unusable), set \
  usable=false and leave excerpt_selected empty.
- Otherwise, select the single most relevant excerpt (a quote or tight \
  paraphrase, 1-4 sentences) that could ground a claim in the article.
- Write relevance_notes explaining specifically why this excerpt matters for \
  this request — never a generic statement like "this source is relevant".

Only use text that is actually present in the raw content. Never invent or \
infer facts not in the source."""


def build_user_message(*, raw_idea: str | None, target_audience: str, sources: list[dict]) -> str:
    source_blocks = "\n\n".join(
        f"--- source_id: {s['id']} ---\nurl: {s['url']}\nraw_content:\n{s['raw_content'][:8000]}"
        for s in sources
    )
    return (
        f"Content idea: {raw_idea or '(none provided)'}\n"
        f"Target audience: {target_audience}\n\n"
        f"Sources:\n{source_blocks}"
    )
