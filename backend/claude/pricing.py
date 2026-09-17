"""Anthropic per-token pricing, USD per 1,000,000 tokens. Kept as a plain
dict, not fetched live — the API doesn't expose current pricing, so this has
to be updated by hand when Anthropic changes rates. Source: platform.claude.com/docs/en/about-claude/pricing.
"""

from claude.models import HAIKU, OPUS, SONNET

PRICE_PER_MILLION_USD: dict[str, dict[str, float]] = {
    OPUS: {"input": 5.00, "output": 25.00},
    SONNET: {"input": 2.00, "output": 10.00},
    HAIKU: {"input": 1.00, "output": 5.00},
}


def cost_usd(*, model: str, input_tokens: int, output_tokens: int) -> float:
    """Returns 0.0 for an unrecognized model rather than raising — a pricing
    lookup miss must never take down the actual Claude call it's costing."""
    rates = PRICE_PER_MILLION_USD.get(model)
    if not rates:
        return 0.0
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
