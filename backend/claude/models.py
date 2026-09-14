"""The model router — decided 2026-09-14, see docs/work/BUILD_LOG.md.

Tiered by step:
- `generate` and `evaluate` use Sonnet: these are the quality-sensitive steps.
  `generate` produces the actual article the audience reads and that has to
  satisfy SEO rules and stay source-grounded; `evaluate` drives the revision
  loop (test scenario 4) — a weak evaluator model here is the single biggest
  risk to the whole self-review mechanism (see EDGE_CASES.md #17: a
  false-pass evaluation defeats the loop entirely).
- `research` and `adapt` use Haiku: research's job here is summarizing/
  extracting from already-scraped text and picking relevant excerpts, not
  original writing. `adapt` is mostly rule application (PAS structure, char
  limits, plain-text vs. html) against an already-approved, already-good
  article — the hard creative work already happened in `generate`.
- `plan` uses Haiku: outlining from a fixed set of sources is structured,
  not creative.

Changing a step's model is a one-line change here — nowhere else imports a
model name directly.
"""

from shared.enums import JobType

SONNET = "claude-sonnet-5"
HAIKU = "claude-haiku-4-5-20251001"

MODEL_FOR_STEP: dict[JobType, str] = {
    JobType.RESEARCH: HAIKU,
    JobType.PLAN: HAIKU,
    JobType.GENERATE: SONNET,
    JobType.EVALUATE: SONNET,
    JobType.ADAPT: HAIKU,
}


def model_for(step: JobType) -> str:
    return MODEL_FOR_STEP[step]
