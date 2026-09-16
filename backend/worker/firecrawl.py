"""Firecrawl scrape client — decided 2026-09-14 (see BUILD_LOG.md) over direct
HTTP/Crawl4AI: handles JS-rendered pages without custom extraction code.
"""

import httpx

from app.config import get_settings

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"
FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v2/search"


class ScrapeFailure(Exception):
    pass


class SearchFailure(Exception):
    pass


def search_web(query: str, limit: int = 3, timeout_seconds: float = 30.0) -> list[dict]:
    """Returns up to `limit` results as [{"url": str, "title": str | None,
    "raw_content": str}], fetched with page content already included
    (scrapeOptions) so no separate scrape_url call is needed. Raises
    SearchFailure on any non-2xx response or transport error. Results with
    no usable markdown are dropped rather than raising, since a partial
    result set is still useful (mirrors scrape_url's "empty is unusable"
    rule, applied per-result instead of to the whole call)."""
    settings = get_settings()
    try:
        response = httpx.post(
            FIRECRAWL_SEARCH_URL,
            headers={"Authorization": f"Bearer {settings.firecrawl_api_key}"},
            json={"query": query, "limit": limit, "scrapeOptions": {"formats": ["markdown"]}},
            timeout=timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise SearchFailure(f"request to Firecrawl search failed for {query!r}: {exc}") from exc

    if response.status_code != 200:
        raise SearchFailure(f"Firecrawl search returned {response.status_code} for {query!r}: {response.text[:500]}")

    results = response.json().get("data", {}).get("web", [])
    usable = []
    for result in results:
        markdown = (result.get("markdown") or "").strip()
        url = result.get("url")
        if not markdown or not url:
            continue
        usable.append({"url": url, "title": result.get("title"), "raw_content": markdown})
    return usable


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
