"""DuckDuckGo search wrapper — max 5 results, 5s timeout per query."""
import logging
import concurrent.futures

from duckduckgo_search import DDGS

log = logging.getLogger("web_search")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="ddg")

MAX_RESULTS = 5


def _search_sync(query: str) -> list[dict]:
    try:
        with DDGS() as ddg:
            results = list(ddg.text(query, max_results=MAX_RESULTS))
        return [{"title": r.get("title", ""), "body": r.get("body", ""), "url": r.get("href", "")} for r in results]
    except Exception as e:
        log.warning("DDG search failed for %r: %s", query, e)
        return []


async def search(query: str, timeout: float = 5.0) -> list[dict]:
    """Run a DDG search in a thread pool with timeout. Returns list of {title, body, url}."""
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        results = await asyncio.wait_for(
            loop.run_in_executor(_executor, _search_sync, query),
            timeout=timeout,
        )
        log.info("DDG %r → %d results", query, len(results))
        return results
    except asyncio.TimeoutError:
        log.warning("DDG search timed out for %r", query)
        return []
