TONE_GUIDANCE = """

Voice: write like a person posting this themselves, not like an AI summarizing
the article. Avoid em dashes; use commas or periods instead. Vary sentence
length and don't lean on any one sentence pattern."""

SYSTEM_BY_CHANNEL = {
    "linkedin": """Adapt the approved article into a LinkedIn post.

Rules (channel-formatting-rules.md):
- Use the PAS structure: problem, agitation, solution.
- Keep paragraphs short.
- Use bullets or simple symbols where they improve clarity.
- Use a small number of relevant emojis only if they fit the brand voice —
  never more than a few.
- End with a clear call to action.

Output plain text — no markdown syntax (no **, ##, etc.); LinkedIn renders
markdown as literal characters. Do not introduce any claim, statistic, or
example that isn't already in the source article. content_format must be
"plain_text". formatting_check must include char_count, within_limit
(LinkedIn practical limit: 3000 chars), and emoji_count.""",
    "x": """Adapt the approved article into a single X (Twitter) post.

Rules (channel-formatting-rules.md):
- Lead with the main benefit, insight, or hook.
- Keep it focused on one core idea.
- Use line breaks for readability.
- Use no more than 1-2 relevant hashtags.
- Only tag an account if the tag adds real value (usually: don't).

HARD LIMIT: the content field must be 280 characters or fewer, counting every
character including spaces, punctuation, and hashtags. This is a strict
platform limit, not a guideline — count your output before finalizing it and
cut anything necessary (a hashtag, a clause, an example) to stay at or under
280. Never write a longer draft and rely on this being trimmed for you.

Output plain text — no markdown syntax. Do not introduce any claim not
already in the source article. content_format must be "plain_text".
formatting_check must include char_count, within_limit (<=280), and
hashtag_count (<=2).""",
    "newsletter": """Adapt the approved article into an email newsletter.

Rules (channel-formatting-rules.md):
- Strong subject line with a clear benefit or point of intrigue.
- Short intro, 1-3 sentences.
- Main value section easy to skim — subheadings or bullets.
- Optional secondary item (quick tip, link, update).
- Clear call to action.
- Friendly sign-off.
- Write for a smart, busy reader.
- Total body length between 250 and 600 words.

Output valid HTML (content_format = "html") — most email clients need HTML,
not markdown. Include the subject line as the first field inside content
(e.g. a leading <h1> or comment marking it), and also report it in
formatting_check.subject_line. Do not introduce any claim not already in the
source article. formatting_check must include word_count, within_word_range,
and subject_line.""",
}


def build_user_message(
    *,
    article_title: str,
    article_body_markdown: str,
    target_audience: str,
    revision_instructions: str | None = None,
    previous_content: str | None = None,
) -> str:
    parts = [
        f"Target audience: {target_audience}",
        f"Approved article title: {article_title}",
        f"Approved article body:\n{article_body_markdown}",
    ]
    if revision_instructions:
        parts.append(f"Rewrite instructions from the author: {revision_instructions}")
        parts.append(f"Previous adaptation for this channel (improve on this, don't just repeat it):\n{previous_content}")
    return "\n\n".join(parts)
