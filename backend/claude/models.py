"""The model router — decided 2026-09-14, re-tiered 2026-09-17, see
docs/work/BUILD_LOG.md.

Tiered by step:
- `research`, `plan`, and `generate` use Sonnet: research and planning are
  working from a fixed set of already-scraped sources toward a plan the rest
  of the pipeline depends on, and `generate` produces the actual article the
  audience reads and that has to satisfy SEO rules and stay source-grounded —
  all three warrant a genuinely strong model, not just structured extraction.
- `evaluate` uses Opus: it drives the revision loop (test scenario 4) and is
  the one step whose entire job is judgment — grounding claims against
  sources, catching overstated or misinterpreted evidence, staying consistent
  across revisions. A weak evaluator model here is the single biggest risk to
  the whole self-review mechanism (see EDGE_CASES.md #17: a false-pass
  evaluation defeats the loop entirely) — this step gets the strongest model
  in the tier for exactly that reason.
- `adapt` uses Haiku: mostly rule application (PAS structure, char limits,
  plain-text vs. html) against an already-approved, already-good article —
  format conversion, not deep reasoning; the hard creative work already
  happened in `generate`.
- `gather_evidence` uses Sonnet: verifying whether one candidate source
  actually supports one specific claim (claude/prompts/verify_evidence.py)
  is a bounded, well-specified judgment call, not open-ended reasoning — the
  same tier as research/planning. The real backstop against a bad
  verification isn't model tier, it's mechanical: gather_evidence.py checks
  the model's claimed excerpt is actually present in the source's real
  retrieved content before trusting it at all.

Escalation: when an evaluation flags unsupported claims — a fundamental
source-interpretation problem, not just weak wording — those claims are
routed through evidence-driven regeneration (worker/handlers/gather_evidence.py)
rather than a plain reword, and the regeneration that follows is escalated
to Opus via `escalated_model` in the generate job's payload
(worker/handlers/generate.py reads it and passes it through to
`generate_draft(model=...)` instead of the default Sonnet). Weak-but-nonspecific
grounding (no named claims to research) still escalates directly to Opus
without the evidence-gathering detour, since there's nothing concrete to
look up.

Changing a step's default model is a one-line change here — nowhere else
imports a model name directly.
"""

from shared.enums import JobType

SONNET = "claude-sonnet-5"
OPUS = "claude-opus-5"
HAIKU = "claude-haiku-4-5-20251001"

MODEL_FOR_STEP: dict[JobType, str] = {
    JobType.RESEARCH: SONNET,
    JobType.PLAN: SONNET,
    JobType.GENERATE: SONNET,
    JobType.EVALUATE: OPUS,
    JobType.ADAPT: HAIKU,
    JobType.GATHER_EVIDENCE: SONNET,
}


def model_for(step: JobType) -> str:
    return MODEL_FOR_STEP[step]
