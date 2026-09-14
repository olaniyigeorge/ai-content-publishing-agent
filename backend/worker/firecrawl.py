"""Firecrawl scrape client — decided 2026-09-14 (see BUILD_LOG.md) over direct
HTTP/Crawl4AI: handles JS-rendered pages without custom extraction code.
"""

import httpx

from app.config import get_settings

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"


class ScrapeFailure(Exception):
    pass


def scrape_url(url: str, timeout_seconds: float = 30.0) -> dict:
    """Returns {"title": str | None, "raw_content": str}. Raises
    ScrapeFailure on any non-2xx response, timeout, or empty/unusable
    content — EDGE_CASES.md #6/#7/#8: a failed or empty scrape must be
    visible, never silently treated as a real source."""
    settings = get_settings()
    try:
        response = httpx.post(
            FIRECRAWL_SCRAPE_URL,
            headers={"Authorization": f"Bearer {settings.firecrawl_api_key}"},
            json={"url": url, "formats": ["markdown"]},
            timeout=timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise ScrapeFailure(f"request to Firecrawl failed for {url}: {exc}") from exc

    if response.status_code != 200:
        raise ScrapeFailure(f"Firecrawl returned {response.status_code} for {url}: {response.text[:500]}")

    data = response.json().get("data", {})
    markdown = (data.get("markdown") or "").strip()
    if not markdown:
        raise ScrapeFailure(f"Firecrawl returned no usable content for {url}")

    return {"title": (data.get("metadata") or {}).get("title"), "raw_content": markdown}
