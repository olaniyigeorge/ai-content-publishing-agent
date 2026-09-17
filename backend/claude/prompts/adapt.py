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

Output a complete, self-contained HTML email (content_format = "html") that
follows the Koya email design system below exactly — this keeps every
newsletter visually consistent instead of reinventing a layout each time.
Email clients strip <style> blocks and external CSS unreliably, so every
rule below must be an inline `style="..."` attribute, not a class or a
<style> tag. Use a table-based layout (email-safe); do not use <div> flexbox/
grid, which many clients ignore.

KOYA EMAIL DESIGN SYSTEM (mirrors the Koya dashboard's own tokens: a deep
neutral surface with a single blue accent — #3B82F6 — used for the header,
links, and calls to action, kept here on a light background since email
clients render dark-mode unreliably):
- Root: a single centered <table role="presentation" width="100%"
  cellpadding="0" cellspacing="0" style="background-color:#f4f4f7;padding:32px 16px;font-family:Arial,Helvetica,sans-serif;">
  containing one inner <table role="presentation" width="600"
  style="max-width:600px;margin:0 auto;background-color:#ffffff;border-radius:12px;overflow:hidden;">.
- Header band: a <tr><td style="background-color:#3B82F6;padding:24px 32px;">
  with "Koya" in <span style="color:#ffffff;font-size:18px;font-weight:700;letter-spacing:0.5px;">.
- Body cell: <td style="padding:32px;color:#1f2937;font-size:15px;line-height:1.6;">.
  - Intro paragraph: <p style="margin:0 0 20px;font-size:16px;color:#1f2937;">.
  - Section subheadings: <h2 style="margin:24px 0 8px;font-size:18px;color:#111827;">.
  - Body paragraphs: <p style="margin:0 0 16px;">.
  - Bullets: <ul style="margin:0 0 16px;padding-left:20px;"><li style="margin:0 0 8px;">.
  - Optional secondary item: wrap in <table role="presentation" width="100%"
    style="background-color:#EFF6FF;border-radius:8px;margin:24px 0;"><tr><td style="padding:16px;">.
  - Call-to-action button: <table role="presentation"><tr><td style="border-radius:6px;background-color:#3B82F6;">
    <a href="#" style="display:inline-block;padding:12px 24px;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;">CTA TEXT</a></td></tr></table>
    (use a real link if the source article/sources supply one, otherwise "#").
  - Sign-off: <p style="margin:24px 0 0;color:#1f2937;">.
- Footer band: <tr><td style="padding:20px 32px;background-color:#f4f4f7;color:#9ca3af;font-size:12px;text-align:center;">
  "You're receiving this because you subscribed to Koya updates." — no unsubscribe link needed for this exercise.

Return this whole HTML document as the content field, starting with
<!doctype html>. Include the subject line as an HTML comment
<!-- subject: ... --> as the very first line of content, and also report it
in formatting_check.subject_line. Do not introduce any claim not already in
the source article. formatting_check must include word_count,
within_word_range, and subject_line.""",
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
