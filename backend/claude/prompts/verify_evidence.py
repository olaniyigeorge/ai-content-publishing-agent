"""Evidence verification: given one specific claim and one candidate
source's raw retrieved content, decide whether that source actually
supports the claim — not just whether it exists or is on-topic. Runs once
per (claim, candidate) pair from worker/handlers/gather_evidence.py, before
that candidate is ever trusted enough to reach the generator.
"""

SYSTEM = """You are a fact-checker. You are given one specific claim from a \
draft article and the raw content of one candidate source. Decide whether \
this source actually supports the claim — not just whether it's on the \
same general topic.

- supports_claim=true only if the source states something that directly \
  backs the claim (the same fact, statistic, or conclusion, possibly in \
  different words) — not merely related, adjacent, or plausible.
- If true, copy the supporting passage into `excerpt` EXACTLY as it \
  appears in the given source content. Do not paraphrase, summarize, \
  translate, or shorten it beyond selecting a contiguous span verbatim. \
  Never write an excerpt that isn't a real quote from the content you were \
  given.
- If the source doesn't support the claim (wrong topic, contradicts it, \
  only tangentially related, or too vague to actually count as support), \
  set supports_claim=false and leave excerpt empty.
- Explain your reasoning briefly in `reason` either way."""


def build_user_message(*, claim_text: str, source_title: str | None, source_url: str, source_content: str) -> str:
    return (
        f"Claim to verify: {claim_text}\n\n"
        f"Candidate source: {source_title or '(untitled)'} ({source_url})\n\n"
        f"Source content:\n{source_content[:8000]}"
    )
