"""Wikipedia REST API — no key required."""
import asyncio
import logging
import urllib.parse

import httpx

log = logging.getLogger("wiki_search")

_BASE = "https://en.wikipedia.org/api/rest_v1/page/summary"
_EXTRACT_URL = "https://en.wikipedia.org/w/api.php"
_TIMEOUT = 8.0


async def fetch_summary(topic: str) -> str:
    """Fetch Wikipedia intro extract for topic. Returns empty string on failure."""
    encoded = urllib.parse.quote(topic.replace(" ", "_"))
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            # First try: REST summary (fast, ~300 words)
            r = await client.get(f"{_BASE}/{encoded}", follow_redirects=True)
            if r.status_code == 200:
                data = r.json()
                extract = data.get("extract", "").strip()
                if len(extract) > 100:
                    log.info("Wikipedia summary OK for %r (%d chars)", topic, len(extract))
                    return extract

            # Fallback: search API for better title match
            r2 = await client.get(_EXTRACT_URL, params={
                "action": "query",
                "list": "search",
                "srsearch": topic,
                "srlimit": 1,
                "format": "json",
            })
            if r2.status_code != 200:
                return ""
            results = r2.json().get("query", {}).get("search", [])
            if not results:
                return ""

            title = results[0]["title"]
            encoded2 = urllib.parse.quote(title.replace(" ", "_"))
            r3 = await client.get(f"{_BASE}/{encoded2}", follow_redirects=True)
            if r3.status_code == 200:
                data3 = r3.json()
                extract3 = data3.get("extract", "").strip()
                log.info("Wikipedia fallback OK: %r → %r (%d chars)", topic, title, len(extract3))
                return extract3

        except Exception as e:
            log.warning("Wikipedia fetch failed for %r: %s", topic, e)
    return ""
