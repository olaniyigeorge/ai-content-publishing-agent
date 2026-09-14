"""Mock publishing adapter (architecture.md §7/§9.7) — no real LinkedIn/X/
Mailgun credentials in v1. This is the only place that "publishes"; the
publish job handler doesn't know it's a mock.

Includes a deliberate force-failure hook so the dead-letter path is
demonstrable for the Loom video (EDGE_CASES.md #40) without needing a real
upstream outage.
"""


class PublishFailure(Exception):
    pass


FORCE_FAIL_MARKER = "[[force-publish-failure]]"


def publish(channel: str, content: str) -> None:
    if FORCE_FAIL_MARKER in content:
        raise PublishFailure(f"{channel} adapter (mock): simulated upstream failure")
    # Real integration point: call the LinkedIn/X API, or send the newsletter
    # via the email provider. For v1 this deterministically succeeds.
    return None
