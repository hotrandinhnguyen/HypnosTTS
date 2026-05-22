"""Image generation via OpenAI DALL-E 3 API."""
import logging

import httpx
from openai import AsyncOpenAI

from app.backend.config import OPENAI_API_KEY, DALLE_MODEL, DALLE_SIZE, DALLE_QUALITY

log = logging.getLogger("image_gen_dalle")

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def generate(prompt: str) -> bytes:
    log.info("[DALL-E] generating — model=%s size=%s quality=%s", DALLE_MODEL, DALLE_SIZE, DALLE_QUALITY)
    resp = await _client.images.generate(
        model=DALLE_MODEL,
        prompt=prompt,
        size=DALLE_SIZE,
        quality=DALLE_QUALITY,
        n=1,
    )
    url = resp.data[0].url
    async with httpx.AsyncClient(timeout=60) as http:
        r = await http.get(url)
        r.raise_for_status()
    log.info("[DALL-E] done — %d bytes", len(r.content))
    return r.content
