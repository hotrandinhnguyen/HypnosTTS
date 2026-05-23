"""
Image generation + Remotion render server — runs on Lightning.ai (GPU).

POST /generate        {"prompt"}                          → PNG bytes
POST /generate_save   {"prompt","session_id","img_idx"}   → {"url","path"}
POST /unload                                              → {"status","vram_gb"}
POST /render          {session_id,n_images,audio_b64,...} → MP4 bytes
GET  /health                                              → {"status","vram_gb"}
GET  /files/{session_id}/...                              → static session files
"""
import asyncio
import base64
import io
import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path

import torch
import uvicorn
from diffusers import StableDiffusion3Pipeline
from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("image_server")

MODEL      = os.getenv("SD_MODEL",  "stabilityai/stable-diffusion-3.5-medium")
STEPS      = int(os.getenv("SD_STEPS",  "50"))
WIDTH      = int(os.getenv("SD_WIDTH",  "1024"))
HEIGHT     = int(os.getenv("SD_HEIGHT", "1024"))
CFG        = float(os.getenv("SD_CFG",  "7.0"))
NEG_PROMPT = os.getenv(
    "SD_NEG_PROMPT",
    "blurry, low quality, distorted, deformed, ugly, bad anatomy, "
    "watermark, text, logo, oversaturated, noisy, pixelated",
)
REMOTION_PATH = os.getenv(
    "REMOTION_PATH",
    "/teamspace/studios/this_studio/remotion_server",
)

SESSIONS_DIR = Path("/tmp/remotion_sessions")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.mount("/files", StaticFiles(directory=str(SESSIONS_DIR)), name="files")

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
        log.info("Model ready — VRAM: %.1f GB", torch.cuda.memory_allocated() / 1e9)
    return _pipe


def _infer_and_get_image(prompt: str) -> Image.Image:
    pipe = _load()
    with torch.inference_mode():
        result = pipe(
            prompt=prompt,
            negative_prompt=NEG_PROMPT,
            num_inference_steps=STEPS,
            width=WIDTH,
            height=HEIGHT,
            guidance_scale=CFG,
        )
    return result.images[0]


# ── Pydantic models ───────────────────────────────────────────────────────────

class GenRequest(BaseModel):
    prompt: str


class GenSaveRequest(BaseModel):
    prompt: str
    session_id: str
    img_idx: int


class RenderRequest(BaseModel):
    session_id: str
    n_images: int
    audio_b64: str
    sentences: list[str]
    sentence_timings: list[list[float]]
    image_timings: list[list[float]]
    fps: int = 15
    width: int = 1024
    height: int = 1024


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    await asyncio.get_event_loop().run_in_executor(None, _load)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/generate")
async def generate(req: GenRequest):
    def _run():
        img = _infer_and_get_image(req.prompt)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    log.info("Generating — %s", req.prompt[:80])
    png = await asyncio.get_event_loop().run_in_executor(None, _run)
    log.info("Done — %d bytes", len(png))
    return Response(content=png, media_type="image/png")


@app.post("/generate_save")
async def generate_save(req: GenSaveRequest):
    session_dir = SESSIONS_DIR / req.session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    img_path = session_dir / f"img_{req.img_idx:04d}.png"

    def _run():
        img = _infer_and_get_image(req.prompt)
        img.save(str(img_path))

    log.info("GenerateSave [%s] img_%04d — %s", req.session_id, req.img_idx, req.prompt[:80])
    await asyncio.get_event_loop().run_in_executor(None, _run)
    url = f"http://localhost:8001/files/{req.session_id}/img_{req.img_idx:04d}.png"
    log.info("Saved — %s", img_path)
    return {"url": url, "path": str(img_path)}


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


@app.post("/render")
async def render(req: RenderRequest):
    session_dir = SESSIONS_DIR / req.session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    audio_path = session_dir / "audio.wav"
    audio_path.write_bytes(base64.b64decode(req.audio_b64))

    audio_url = f"http://localhost:8001/files/{req.session_id}/audio.wav"
    images = [
        f"http://localhost:8001/files/{req.session_id}/img_{i:04d}.png"
        for i in range(req.n_images)
    ]

    total_dur = req.sentence_timings[-1][1] if req.sentence_timings else 0
    duration_in_frames = int(total_dur * req.fps) + req.fps  # +1s buffer

    output_path = session_dir / "output.mp4"
    render_args = {
        "durationInFrames": duration_in_frames,
        "fps": req.fps,
        "width": req.width,
        "height": req.height,
        "outputPath": str(output_path),
        "images": images,
        "timings": req.image_timings,
        "sentences": req.sentences,
        "sentenceTimings": req.sentence_timings,
        "audioSrc": audio_url,
    }

    def _do_render():
        log.info("[Render] Starting Remotion — session=%s n_images=%d dur=%.1fs",
                 req.session_id, req.n_images, total_dur)
        result = subprocess.run(
            ["node", f"{REMOTION_PATH}/render.mjs", json.dumps(render_args)],
            capture_output=True,
            timeout=None,
            cwd=REMOTION_PATH,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[-3000:]
            raise RuntimeError(f"Remotion render failed:\n{err}")
        mp4 = output_path.read_bytes()
        shutil.rmtree(str(session_dir), ignore_errors=True)
        log.info("[Render] done — %d bytes", len(mp4))
        return mp4

    mp4 = await asyncio.get_event_loop().run_in_executor(None, _do_render)
    return Response(content=mp4, media_type="video/mp4")


@app.get("/health")
async def health():
    vram = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0
    return {"status": "ok", "model": MODEL, "steps": STEPS, "vram_gb": round(vram, 1)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
