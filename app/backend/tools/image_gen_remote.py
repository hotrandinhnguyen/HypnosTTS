"""Image generation via remote Lightning.ai API."""
import logging

import httpx

from app.backend.config import IMAGE_API_URL

log = logging.getLogger("image_gen_remote")


async def generate(prompt: str) -> bytes:
    log.info("[Remote] generating via %s", IMAGE_API_URL)
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{IMAGE_API_URL}/generate",
            json={"prompt": prompt},
        )
        r.raise_for_status()
    log.info("[Remote] done — %d bytes", len(r.content))
    return r.content
