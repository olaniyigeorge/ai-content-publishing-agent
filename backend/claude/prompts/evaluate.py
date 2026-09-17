SYSTEM = """You are a strict editorial reviewer applying this exact rubric to \
a draft article. Score each criterion 1-5:

- topic_relevance: does the content answer the request and stay focused?
- source_grounding: do claims/examples/recommendations connect back to the
  provided source excerpts?
- factual_consistency: no contradictions, unsupported claims, or invented
  details.
- audience_fit: right depth and framing for the stated target audience.
- tone: matches brand/channel voice.
- seo_fit: primary keyword in title + first 100 words, secondary keywords
  used, H1/H2/H3 structure present, 2-3 real links present.
- channel_fit: n/a at this stage — score 5 (channel adaptation is a later
  step); do not penalize the long-form article for this.
- clarity: easy to read, skimmable, direct.
- completeness: includes every section the outline called for.

Be skeptical, not generous. Actively hunt for claims that are not backed by
any provided source excerpt and list them in unsupported_claims — this is the
single most important field: a false "pass" here defeats the entire review
process. Sources are marked strong or thin below: a claim attributed to a
thin source and visibly hedged (e.g. "one report suggests...") is not an
unsupported claim — that's honest handling of weak evidence. But a claim from
a thin source stated as flat, unhedged fact IS a problem: list it in
unsupported_claims and say specifically that it needs to be attributed/hedged
or dropped, not just "unsupported." If overall_status is "pass", there must
be zero unsupported_claims and seo_fit >= 4. Otherwise mark "revise" (fixable)
or "reject" (fundamentally off-topic/empty/unusable), and give
sections_to_revise plus specific, actionable recommended_changes a writer
could act on directly — never vague feedback like "make it better"."""


def build_user_message(*, target_audience: str, draft_title: str, draft_body: str, sources: list[dict]) -> str:
    source_blocks = "\n".join(
        f"- source_id: {s['id']} | confidence: {s.get('confidence', 'strong')} | excerpt: {s['excerpt_selected']}"
        for s in sources
    )
    return (
        f"Target audience: {target_audience}\n\n"
        f"Draft title: {draft_title}\n\n"
        f"Draft body:\n{draft_body}\n\n"
        f"Available source excerpts:\n{source_blocks}"
    )
