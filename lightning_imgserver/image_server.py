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
from diffusers import FluxPipeline
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

MODEL  = os.getenv("FLUX_MODEL",  "black-forest-labs/FLUX.1-schnell")
STEPS  = int(os.getenv("FLUX_STEPS",  "4"))
WIDTH  = int(os.getenv("FLUX_WIDTH",  "1024"))
HEIGHT = int(os.getenv("FLUX_HEIGHT", "1024"))

app = FastAPI()
_pipe = None
_lock = threading.Lock()


def _load():
    global _pipe
    with _lock:
        if _pipe is not None:
            return _pipe
        log.info("Loading %s …", MODEL)
        pipe = FluxPipeline.from_pretrained(MODEL, torch_dtype=torch.bfloat16)
        pipe.enable_sequential_cpu_offload()
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
                num_inference_steps=STEPS,
                width=WIDTH,
                height=HEIGHT,
                guidance_scale=0.0,
            )
        img: Image.Image = result.images[0]
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    log.info("Generating — %s", req.prompt[:80])
    png = await asyncio.get_event_loop().run_in_executor(None, _infer)
    log.info("Done — %d bytes", len(png))
    return Response(content=png, media_type="image/png")


@app.get("/health")
async def health():
    vram = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0
    return {"status": "ok", "model": MODEL, "steps": STEPS, "vram_gb": round(vram, 1)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
