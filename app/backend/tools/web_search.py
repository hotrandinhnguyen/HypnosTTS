"""Tavily search wrapper for AI-optimised web results."""
import asyncio
import logging
import concurrent.futures

from tavily import TavilyClient
from app.backend.config import TAVILY_API_KEY, DDG_MAX_RESULTS, DDG_TIMEOUT

log = logging.getLogger("web_search")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="tavily")
_client = TavilyClient(api_key=TAVILY_API_KEY)


def _search_sync(query: str) -> list[dict]:
    try:
        response = _client.search(
            query,
            max_results=DDG_MAX_RESULTS,
            search_depth="advanced",
            include_answer=False,
        )
        results = response.get("results", [])
        return [
            {"title": r.get("title", ""), "body": r.get("content", ""), "url": r.get("url", "")}
            for r in results
        ]
    except Exception as e:
        log.warning("Tavily search failed for %r: %s", query, e)
        return []


async def search(query: str) -> list[dict]:
    """Run a Tavily search in a thread pool with timeout. Returns list of {title, body, url}."""
    loop = asyncio.get_event_loop()
    try:
        async with asyncio.timeout(DDG_TIMEOUT):
            results = await loop.run_in_executor(_executor, _search_sync, query)
        log.info("Tavily %r → %d results", query, len(results))
        return results
    except TimeoutError:
        log.warning("Tavily search timed out for %r", query)
        return []
