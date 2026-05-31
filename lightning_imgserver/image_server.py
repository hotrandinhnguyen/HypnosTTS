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
import time
from pathlib import Path

import torch
import uvicorn
from diffusers import StableDiffusion3Pipeline
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
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

I2V_MODEL  = os.getenv("I2V_MODEL",  "stabilityai/stable-video-diffusion-img2vid-xt")
I2V_STEPS  = int(os.getenv("I2V_STEPS",  "25"))
I2V_FPS    = int(os.getenv("I2V_FPS",    "7"))
I2V_FRAMES = int(os.getenv("I2V_FRAMES", "49"))
I2V_WIDTH  = int(os.getenv("I2V_WIDTH",  "768"))
I2V_HEIGHT = int(os.getenv("I2V_HEIGHT", "432"))
REMOTION_PATH = os.getenv(
    "REMOTION_PATH",
    "/teamspace/studios/this_studio/remotion_server",
)

SESSIONS_DIR = Path("/tmp/remotion_sessions")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.mount("/files", StaticFiles(directory=str(SESSIONS_DIR)), name="files")

_pipe     = None
_lock     = threading.Lock()
_i2v_pipe = None
_i2v_lock = threading.Lock()


def _vram_gb() -> float:
    return round(torch.cuda.memory_allocated() / 1e9, 2) if torch.cuda.is_available() else 0.0


def _vram_peak_gb() -> float:
    return round(torch.cuda.max_memory_allocated() / 1e9, 2) if torch.cuda.is_available() else 0.0


def _load():
    global _pipe, _i2v_pipe
    with _lock:
        if _pipe is not None:
            return _pipe
        # Unload I2V model nếu đang load
        with _i2v_lock:
            if _i2v_pipe is not None:
                del _i2v_pipe
                _i2v_pipe = None
                torch.cuda.empty_cache()
                log.info("I2V unloaded for SD — VRAM freed")
        log.info("Loading %s …", MODEL)
        pipe = StableDiffusion3Pipeline.from_pretrained(
            MODEL,
            torch_dtype=torch.float16,
        )
        pipe = pipe.to("cuda")
        pipe.enable_attention_slicing()
        pipe.set_progress_bar_config(disable=True)
        _pipe = pipe
        log.info("Model ready — vram=%.2fGB peak=%.2fGB", _vram_gb(), _vram_peak_gb())
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

def _load_i2v():
    global _i2v_pipe, _pipe
    with _i2v_lock:
        if _i2v_pipe is not None:
            return _i2v_pipe
        with _lock:
            if _pipe is not None:
                del _pipe
                _pipe = None
                torch.cuda.empty_cache()
                log.info("SD unloaded for I2V — VRAM freed")
        from diffusers import StableVideoDiffusionPipeline
        log.info("Loading I2V %s ...", I2V_MODEL)
        pipe = StableVideoDiffusionPipeline.from_pretrained(
            I2V_MODEL, torch_dtype=torch.float16, variant="fp16",
        )
        pipe.to("cuda")
        pipe.enable_attention_slicing()
        pipe.set_progress_bar_config(disable=True)
        _i2v_pipe = pipe
        log.info("I2V ready — vram=%.2fGB peak=%.2fGB", _vram_gb(), _vram_peak_gb())
    return _i2v_pipe


class GenRequest(BaseModel):
    prompt: str


class GenSaveRequest(BaseModel):
    prompt: str
    session_id: str
    img_idx: int


class GenClipRequest(BaseModel):
    session_id: str
    img_idx: int
    duration_s: float
    prompt: str = ""


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
    t0 = time.perf_counter()
    def _run():
        img = _infer_and_get_image(req.prompt)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    log.info("[Image] start prompt=%s steps=%d size=%dx%d vram=%.2fGB", req.prompt[:80], STEPS, WIDTH, HEIGHT, _vram_gb())
    png = await asyncio.get_event_loop().run_in_executor(None, _run)
    log.info("[Image] done sec=%.2f bytes=%d vram=%.2fGB peak=%.2fGB", time.perf_counter() - t0, len(png), _vram_gb(), _vram_peak_gb())
    return Response(content=png, media_type="image/png")


@app.post("/generate_save")
async def generate_save(req: GenSaveRequest):
    t0 = time.perf_counter()
    session_dir = SESSIONS_DIR / req.session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    img_path = session_dir / f"img_{req.img_idx:04d}.png"

    def _run():
        img = _infer_and_get_image(req.prompt)
        img.save(str(img_path))

    log.info(
        "[ImageSave] start session=%s img=%04d steps=%d size=%dx%d vram=%.2fGB prompt=%s",
        req.session_id, req.img_idx, STEPS, WIDTH, HEIGHT, _vram_gb(), req.prompt[:80],
    )
    await asyncio.get_event_loop().run_in_executor(None, _run)
    url = f"http://localhost:8001/files/{req.session_id}/img_{req.img_idx:04d}.png"
    log.info(
        "[ImageSave] done session=%s img=%04d sec=%.2f path=%s vram=%.2fGB peak=%.2fGB",
        req.session_id, req.img_idx, time.perf_counter() - t0, img_path, _vram_gb(), _vram_peak_gb(),
    )
    return {"url": url, "path": str(img_path)}


@app.post("/generate_clip")
async def generate_clip(req: GenClipRequest):
    t0 = time.perf_counter()
    img_path = SESSIONS_DIR / req.session_id / f"img_{req.img_idx:04d}.png"
    if not img_path.exists():
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": f"Image not found: {img_path}"}, status_code=404)

    attempts = [
        (I2V_FRAMES, I2V_WIDTH, I2V_HEIGHT, I2V_STEPS),
        (min(I2V_FRAMES, 33), min(I2V_WIDTH, 768), min(I2V_HEIGHT, 432), I2V_STEPS),
        (25, min(I2V_WIDTH, 768), min(I2V_HEIGHT, 432), max(12, min(I2V_STEPS, 18))),
    ]

    def _run(num_frames: int, width: int, height: int, steps: int):
        import tempfile
        from diffusers.utils import export_to_video
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
        output_fps = max(1, round(num_frames / max(req.duration_s, 0.5)))
        pil_image = Image.open(str(img_path)).convert("RGB").resize((width, height))
        pipe = _load_i2v()
        with torch.inference_mode():
            result = pipe(
                image=pil_image,
                num_frames=num_frames,
                num_inference_steps=steps,
                decode_chunk_size=8,
                motion_bucket_id=100,
            )
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            tmp_path = f.name
        export_to_video(result.frames[0], tmp_path, fps=output_fps)
        clip_bytes = Path(tmp_path).read_bytes()
        Path(tmp_path).unlink(missing_ok=True)
        del result
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return clip_bytes, output_fps

    last_exc: Exception | None = None
    clip = None
    used = None
    for attempt_idx, (num_frames, width, height, steps) in enumerate(attempts, 1):
        output_fps = max(1, round(num_frames / max(req.duration_s, 0.5)))
        log.info(
            "[I2V] start session=%s clip=%04d attempt=%d/%d dur=%.2fs frames=%d fps=%d steps=%d size=%dx%d vram=%.2fGB prompt=%s",
            req.session_id, req.img_idx, attempt_idx, len(attempts), req.duration_s,
            num_frames, output_fps, steps, width, height, _vram_gb(), req.prompt[:80],
        )
        try:
            clip, actual_fps = await asyncio.get_event_loop().run_in_executor(None, _run, num_frames, width, height, steps)
            used = (attempt_idx, num_frames, width, height, steps, actual_fps)
            break
        except torch.OutOfMemoryError as exc:
            last_exc = exc
            log.exception(
                "[I2V] OOM session=%s clip=%04d attempt=%d sec=%.2f vram=%.2fGB peak=%.2fGB",
                req.session_id, req.img_idx, attempt_idx, time.perf_counter() - t0,
                _vram_gb(), _vram_peak_gb(),
            )
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as exc:
            last_exc = exc
            log.exception(
                "[I2V] failed session=%s clip=%04d attempt=%d sec=%.2f vram=%.2fGB peak=%.2fGB",
                req.session_id, req.img_idx, attempt_idx, time.perf_counter() - t0,
                _vram_gb(), _vram_peak_gb(),
            )
            break

    if clip is None or used is None:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        exc = last_exc or RuntimeError("I2V generation failed")
        return JSONResponse(
            {
                "error": type(exc).__name__,
                "detail": str(exc),
                "session_id": req.session_id,
                "img_idx": req.img_idx,
                "vram_gb": _vram_gb(),
                "vram_peak_gb": _vram_peak_gb(),
            },
            status_code=500,
        )

    attempt_idx, num_frames, width, height, steps, output_fps = used
    log.info(
        "[I2V] done session=%s clip=%04d attempt=%d sec=%.2f bytes=%d frames=%d fps=%d steps=%d size=%dx%d vram=%.2fGB peak=%.2fGB",
        req.session_id, req.img_idx, attempt_idx, time.perf_counter() - t0,
        len(clip), num_frames, output_fps, steps, width, height, _vram_gb(), _vram_peak_gb(),
    )
    return Response(content=clip, media_type="video/mp4")


@app.post("/unload")
async def unload():
    t0 = time.perf_counter()
    global _pipe
    with _lock:
        if _pipe is not None:
            del _pipe
            _pipe = None
            torch.cuda.empty_cache()
            log.info("Model unloaded from VRAM")
    vram = _vram_gb()
    log.info("[Unload] done sec=%.2f vram=%.2fGB peak=%.2fGB", time.perf_counter() - t0, vram, _vram_peak_gb())
    return {"status": "unloaded", "vram_gb": vram}


@app.post("/render")
async def render(req: RenderRequest):
    t0 = time.perf_counter()
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
        log.info(
            "[Render] start session=%s n_images=%d dur=%.1fs frames=%d fps=%d size=%dx%d",
            req.session_id, req.n_images, total_dur, duration_in_frames, req.fps, req.width, req.height,
        )
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
        log.info("[Render] done sec=%.2f bytes=%d", time.perf_counter() - t0, len(mp4))
        return mp4

    mp4 = await asyncio.get_event_loop().run_in_executor(None, _do_render)
    return Response(content=mp4, media_type="video/mp4")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL,
        "steps": STEPS,
        "i2v_steps": I2V_STEPS,
        "i2v_frames": I2V_FRAMES,
        "i2v_size": f"{I2V_WIDTH}x{I2V_HEIGHT}",
        "vram_gb": _vram_gb(),
        "vram_peak_gb": _vram_peak_gb(),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
