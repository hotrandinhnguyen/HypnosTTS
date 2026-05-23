"""
Image generation API server — runs on Lightning.ai (GPU).
POST /generate {"prompt": "..."} → PNG bytes
GET  /health                     → {"status": "ok"}

Start: bash start.sh
"""
import io
import logging
import os
import threading

import torch
import uvicorn
from diffusers import StableDiffusion3Pipeline
from fastapi import FastAPI
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("image_server")

MODEL    = os.getenv("SD_MODEL",  "stabilityai/stable-diffusion-3.5-medium")
STEPS    = int(os.getenv("SD_STEPS",  "35"))
WIDTH    = int(os.getenv("SD_WIDTH",  "1024"))
HEIGHT   = int(os.getenv("SD_HEIGHT", "1024"))
CFG      = float(os.getenv("SD_CFG",  "5.0"))
NEG_PROMPT = os.getenv(
    "SD_NEG_PROMPT",
    "blurry, low quality, distorted, deformed, ugly, bad anatomy, "
    "watermark, text, logo, oversaturated, noisy, pixelated",
)

app = FastAPI()
_pipe = None
_lock = threading.Lock()


def _load():
    global _pipe
    with _lock:
        if _pipe is not None:
            return _pipe
        log.info("Loading %s …", MODEL)
        pipe = StableDiffusion3Pipeline.from_pretrained(
            MODEL,
            torch_dtype=torch.float16,
        )
        pipe = pipe.to("cuda")
        pipe.enable_attention_slicing()
        pipe.set_progress_bar_config(disable=True)
        _pipe = pipe
        log.info("Model ready — VRAM: %.1f GB",
                 torch.cuda.memory_allocated() / 1e9)
    return _pipe


class GenRequest(BaseModel):
    prompt: str


@app.on_event("startup")
async def startup():
    import asyncio
    await asyncio.get_event_loop().run_in_executor(None, _load)


@app.post("/generate")
async def generate(req: GenRequest):
    import asyncio

    def _infer():
        pipe = _load()
        with torch.inference_mode():
            result = pipe(
                prompt=req.prompt,
                negative_prompt=NEG_PROMPT,
                num_inference_steps=STEPS,
                width=WIDTH,
                height=HEIGHT,
                guidance_scale=CFG,
            )
        img: Image.Image = result.images[0]
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    log.info("Generating — %s", req.prompt[:80])
    png = await asyncio.get_event_loop().run_in_executor(None, _infer)
    log.info("Done — %d bytes", len(png))
    return Response(content=png, media_type="image/png")


@app.post("/unload")
async def unload():
    global _pipe
    with _lock:
        if _pipe is not None:
            del _pipe
            _pipe = None
            torch.cuda.empty_cache()
            log.info("Model unloaded from VRAM")
    vram = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0
    return {"status": "unloaded", "vram_gb": round(vram, 1)}


@app.get("/health")
async def health():
    vram = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0
    return {"status": "ok", "model": MODEL, "steps": STEPS, "vram_gb": round(vram, 1)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
