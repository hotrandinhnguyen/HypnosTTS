"""Image generation via local diffusion model (default: SDXL-Turbo)."""
import asyncio
import io
import logging
import threading

import torch
from diffusers import AutoPipelineForText2Image
from PIL import Image

from app.backend.config import (
    FLUX_MODEL, FLUX_DEVICE, FLUX_STEPS, FLUX_WIDTH, FLUX_HEIGHT,
)

log = logging.getLogger("image_gen_local")

_pipe = None
_init_lock = threading.Lock()


def _load_pipe_sync():
    global _pipe
    with _init_lock:
        if _pipe is not None:
            return _pipe
        log.info("[ImgGen/local] loading %s on %s …", FLUX_MODEL, FLUX_DEVICE)
        pipe = AutoPipelineForText2Image.from_pretrained(
            FLUX_MODEL,
            torch_dtype=torch.float16,
            variant="fp16",
        ).to(FLUX_DEVICE)
        pipe.set_progress_bar_config(disable=True)
        _pipe = pipe
        log.info("[ImgGen/local] model ready")
    return _pipe


def _infer_sync(prompt: str) -> bytes:
    pipe = _load_pipe_sync()
    with torch.inference_mode():
        result = pipe(
            prompt=prompt,
            num_inference_steps=FLUX_STEPS,
            width=FLUX_WIDTH,
            height=FLUX_HEIGHT,
            guidance_scale=0.0,
        )
    img: Image.Image = result.images[0]
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def generate(prompt: str) -> bytes:
    log.info("[ImgGen/local] generating — steps=%d %dx%d", FLUX_STEPS, FLUX_WIDTH, FLUX_HEIGHT)
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _infer_sync, prompt)
    log.info("[ImgGen/local] done — %d bytes", len(data))
    return data
