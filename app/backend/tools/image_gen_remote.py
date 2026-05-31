"""Image generation and video rendering through the remote Lightning API."""
import base64
import logging
import time

import httpx

from app.backend.config import IMAGE_API_URL

log = logging.getLogger("image_gen_remote")

_TIMEOUT_GEN = 120
_TIMEOUT_CLIP = 900
_TIMEOUT_RENDER = 3600


async def generate(prompt: str) -> bytes:
    t0 = time.perf_counter()
    log.info("[Remote/Image] start url=%s prompt=%s", IMAGE_API_URL, prompt[:80])
    async with httpx.AsyncClient(timeout=_TIMEOUT_GEN) as client:
        r = await client.post(f"{IMAGE_API_URL}/generate", json={"prompt": prompt})
        r.raise_for_status()
    log.info("[Remote/Image] done sec=%.2f bytes=%d", time.perf_counter() - t0, len(r.content))
    return r.content


async def generate_save(prompt: str, session_id: str, img_idx: int) -> str:
    """Generate image and save it to Lightning disk. Returns the image URL."""
    t0 = time.perf_counter()
    log.info("[Remote/ImageSave] start session=%s img=%04d prompt=%s", session_id, img_idx, prompt[:80])
    async with httpx.AsyncClient(timeout=_TIMEOUT_GEN) as client:
        r = await client.post(
            f"{IMAGE_API_URL}/generate_save",
            json={"prompt": prompt, "session_id": session_id, "img_idx": img_idx},
        )
        r.raise_for_status()
    url = r.json()["url"]
    log.info(
        "[Remote/ImageSave] done session=%s img=%04d sec=%.2f url=%s",
        session_id,
        img_idx,
        time.perf_counter() - t0,
        url,
    )
    return url


async def generate_clip(
    session_id: str,
    img_idx: int,
    duration_s: float,
    prompt: str = "",
) -> bytes:
    """Generate an I2V clip from a saved image on Lightning. Returns MP4 bytes."""
    t0 = time.perf_counter()
    payload = {
        "session_id": session_id,
        "img_idx": img_idx,
        "duration_s": duration_s,
        "prompt": prompt,
    }
    log.info(
        "[Remote/I2V] start session=%s clip=%04d dur=%.2fs prompt=%s",
        session_id,
        img_idx,
        duration_s,
        prompt[:80],
    )
    async with httpx.AsyncClient(timeout=_TIMEOUT_CLIP) as client:
        r = await client.post(f"{IMAGE_API_URL}/generate_clip", json=payload)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError:
            log.error(
                "[Remote/I2V] failed session=%s clip=%04d status=%d body=%s",
                session_id,
                img_idx,
                r.status_code,
                r.text[-2000:],
            )
            raise
    log.info(
        "[Remote/I2V] done session=%s clip=%04d sec=%.2f bytes=%d",
        session_id,
        img_idx,
        time.perf_counter() - t0,
        len(r.content),
    )
    return r.content


async def unload() -> None:
    """Free SD model from VRAM after image generation is complete."""
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{IMAGE_API_URL}/unload")
        r.raise_for_status()
    log.info("[Remote/Unload] done sec=%.2f response=%s", time.perf_counter() - t0, r.json())


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
    t0 = time.perf_counter()
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
    log.info(
        "[Remote/Render] start session=%s n_images=%d fps=%d size=%dx%d",
        session_id,
        n_images,
        fps,
        width,
        height,
    )
    async with httpx.AsyncClient(timeout=_TIMEOUT_RENDER) as client:
        r = await client.post(f"{IMAGE_API_URL}/render", json=payload)
        r.raise_for_status()
    log.info(
        "[Remote/Render] done session=%s sec=%.2f bytes=%d",
        session_id,
        time.perf_counter() - t0,
        len(r.content),
    )
    return r.content
