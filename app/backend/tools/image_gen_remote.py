"""Image generation and video render via remote Lightning.ai API."""
import base64
import logging

import httpx

from app.backend.config import IMAGE_API_URL

log = logging.getLogger("image_gen_remote")

_TIMEOUT_GEN    = 120   # seconds per image
_TIMEOUT_RENDER = 3600  # seconds for full Remotion render (10-min video ~20-30min to render)


async def generate(prompt: str) -> bytes:
    log.info("[Remote] generating via %s", IMAGE_API_URL)
    async with httpx.AsyncClient(timeout=_TIMEOUT_GEN) as client:
        r = await client.post(f"{IMAGE_API_URL}/generate", json={"prompt": prompt})
        r.raise_for_status()
    log.info("[Remote] done — %d bytes", len(r.content))
    return r.content


async def generate_save(prompt: str, session_id: str, img_idx: int) -> str:
    """Generate image and save to Lightning disk. Returns the image URL."""
    async with httpx.AsyncClient(timeout=_TIMEOUT_GEN) as client:
        r = await client.post(
            f"{IMAGE_API_URL}/generate_save",
            json={"prompt": prompt, "session_id": session_id, "img_idx": img_idx},
        )
        r.raise_for_status()
    url = r.json()["url"]
    log.info("[Remote] saved img_%04d → %s", img_idx, url)
    return url


async def unload() -> None:
    """Free SD model from VRAM after image generation is complete."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{IMAGE_API_URL}/unload")
        r.raise_for_status()
    log.info("[Remote] model unloaded — %s", r.json())


async def render_video(
    session_id: str,
    n_images: int,
    image_timings: list[tuple[float, float]],
    sentences: list[str],
    sentence_timings: list[tuple[float, float]],
    audio_bytes: bytes,
    fps: int = 25,
    width: int = 1024,
    height: int = 1024,
) -> bytes:
    """Trigger Remotion render on Lightning. Returns MP4 bytes."""
    payload = {
        "session_id": session_id,
        "n_images": n_images,
        "audio_b64": base64.b64encode(audio_bytes).decode(),
        "sentences": sentences,
        "sentence_timings": [[s, e] for s, e in sentence_timings],
        "image_timings": [[s, e] for s, e in image_timings],
        "fps": fps,
        "width": width,
        "height": height,
    }
    log.info("[Remote] render session=%s n_images=%d", session_id, n_images)
    async with httpx.AsyncClient(timeout=_TIMEOUT_RENDER) as client:
        r = await client.post(f"{IMAGE_API_URL}/render", json=payload)
        r.raise_for_status()
    log.info("[Remote] render done — %d bytes", len(r.content))
    return r.content
