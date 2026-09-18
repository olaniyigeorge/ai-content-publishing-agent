"""Intake plausibility check: a cheap second layer behind
app/services/intake_guards.py's free, deterministic checks. Those catch the
mechanically obvious cases (no letters, mashed keys, no vowels) but can be
beaten by any string with one vowel and a few whitespace-separated tokens —
this catches what gets past that filter, before a research/plan/generate/
evaluate run is spent on it.
"""

SYSTEM = """You are a fast pre-check for a content publishing pipeline. You are \
given a raw content idea and a target audience submitted by a content \
manager. Decide whether this looks like a real, usable content request — \
not whether it's a *good* idea, just whether there's an actual discernible \
topic and audience here that a writer could research and write about.

Say plausible=false only for gibberish, keyboard-mashed text, or text with \
no discernible topic or audience at all. A terse, vague, unusual, technical, \
or niche idea is still plausible — err toward plausible=true unless the text \
is clearly nonsense. Being wrong in this direction (letting something odd \
through) costs a normal pipeline run; being wrong the other way blocks a \
real user's real request, which is worse.

Give a one-sentence reason either way: if plausible, name the actual topic/ \
audience you can see in it; if not, say specifically what makes it unusable."""


def build_user_message(*, raw_idea: str | None, target_audience: str) -> str:
    return f"""Raw idea: {raw_idea or "(none — request may rely on an attachment/source URL instead)"}
Target audience: {target_audience}"""
