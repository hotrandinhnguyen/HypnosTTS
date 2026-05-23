"""
Video generation pipeline:
  LangGraph (Researcher → Analogy → Writer → Reviewer)
  → image prompt generation (LLM)
  → image gen + TTS in parallel
  → video assembly (Remotion on Lightning when IMAGE_PROVIDER=remote, else local ffmpeg)
"""
import asyncio
import json
import logging
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import AsyncIterator

from app.backend.config import (
    REF_AUDIO_PATH, REF_TEXT_PATH, TTS_NUM_STEPS, TTS_INSTRUCT,
    BG_MUSIC_PATH, IMAGE_PROVIDER,
)
from app.backend.graph import build_graph
import app.backend.tts_engine as tts_engine
import app.backend.tools.image_gen_remote as remote_gen
from app.backend.agents.image_prompter import generate_image_prompts
from app.backend.tools.image_gen import generate_image
from app.backend.tools.video_assembler import (
    concat_wavs,
    compute_sentence_timings,
    map_image_timings,
    generate_srt,
    assemble_video,
)

log = logging.getLogger("video_pipeline")

_graph    = build_graph()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-tts")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[^\s])|(?<=\.)\s*\n+")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ref_text() -> str:
    if REF_TEXT_PATH.exists():
        return REF_TEXT_PATH.read_text(encoding="utf-8").strip()
    return ""


def _split_sentences(script: str) -> list[str]:
    return [p.strip() for p in _SENTENCE_SPLIT.split(script) if len(p.strip()) >= 4]


async def _synthesize_one(text: str, instruct: str) -> bytes:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: tts_engine.synthesize(
            text, str(REF_AUDIO_PATH), _ref_text(), instruct, TTS_NUM_STEPS
        ),
    )


def _graph_status(event: dict) -> str:
    status = event.get("status", "")
    if status == "researched":
        return "Đang tạo phép ẩn dụ..."
    if status == "analogy_done":
        return "Đang viết bài giảng..."
    if status == "written" and event.get("revision_count", 0) > 0:
        return f"Đang viết lại (lần {event['revision_count']})..."
    if status == "reviewed":
        review = event.get("review") or {}
        if not review.get("passed") and event.get("revision_count", 0) < 2:
            return "Đang tinh chỉnh kịch bản..."
    return ""


# ── TTS ───────────────────────────────────────────────────────────────────────

async def _run_tts_all(sentences: list[str], instruct: str) -> list[bytes]:
    results: list[bytes] = []
    for i, sent in enumerate(sentences, 1):
        log.info("[Video/TTS] %d/%d", i, len(sentences))
        wav = await _synthesize_one(sent, instruct)
        results.append(wav)
    return results


# ── Image gen (local ffmpeg path) ─────────────────────────────────────────────

async def _run_image_gen_local(image_prompts: list[dict]) -> list[bytes]:
    images: list[bytes] = []
    for i, p in enumerate(image_prompts):
        png = await generate_image(p["prompt"])
        log.info("[Video/ImgGen] %d/%d done", i + 1, len(image_prompts))
        images.append(png)
    return images


# ── Image gen (remote path — saves to Lightning disk) ─────────────────────────

async def _run_image_gen_remote(image_prompts: list[dict], session_id: str) -> None:
    for i, p in enumerate(image_prompts):
        await remote_gen.generate_save(p["prompt"], session_id, i)
        log.info("[Video/ImgGen] %d/%d saved to Lightning", i + 1, len(image_prompts))


# ── Main entry ────────────────────────────────────────────────────────────────

async def run_video(topic: str, instruct: str = TTS_INSTRUCT, n_images: int = 0, duration_minutes: int = 0) -> AsyncIterator[dict]:
    """
    Yields:
      {"type": "status",     "data": str}    — progress messages
      {"type": "video_done", "video": bytes}  — final MP4 bytes
      {"type": "error",      "data": str}     — on failure
    """
    t0 = time.perf_counter()
    log.info("[VideoPipeline] START topic=%r provider=%s", topic, IMAGE_PROVIDER)

    # ── Phase 1: LangGraph ───────────────────────────────────────────────────
    yield {"type": "status", "data": "Đang nghiên cứu chủ đề..."}

    initial_state = {
        "topic": topic, "instruct": instruct,
        "target_minutes": duration_minutes,
        "research": None, "analogy": None,
        "script": None, "review": None,
        "revision_count": 0, "status": "",
    }

    state = None
    async for event in _graph.astream(initial_state, stream_mode="values"):
        msg = _graph_status(event)
        if msg:
            yield {"type": "status", "data": msg}
        state = event

    if not state or not state.get("script"):
        yield {"type": "error", "data": "Không tạo được kịch bản."}
        return

    script = state["script"]
    sentences = _split_sentences(script)
    log.info("[VideoPipeline] graph done %.2fs — %d sentences", time.perf_counter() - t0, len(sentences))

    # ── Phase 2: Image prompt generation ────────────────────────────────────
    estimated_duration = len(sentences) * 5.5
    yield {"type": "status", "data": f"Kịch bản {len(sentences)} câu. Đang tạo prompt ảnh..."}
    image_prompts = await generate_image_prompts(sentences, topic, total_duration=estimated_duration, n_images=n_images)
    n_img = len(image_prompts)
    log.info("[VideoPipeline] %d image prompts", n_img)

    # ── Phase 3–6: branch on IMAGE_PROVIDER ──────────────────────────────────
    if IMAGE_PROVIDER == "remote":
        async for event in _remote_render_flow(
            sentences, image_prompts, n_img, instruct, t0, topic
        ):
            yield event
    else:
        async for event in _local_render_flow(
            sentences, image_prompts, n_img, instruct, t0, topic
        ):
            yield event


async def _remote_render_flow(sentences, image_prompts, n_img, instruct, t0, topic):
    """Remote flow: images saved to Lightning → unload model → Remotion render."""
    session_id = uuid.uuid4().hex[:8]

    # Phase 3: TTS (local) + image gen (Lightning) in parallel
    yield {"type": "status", "data": f"Đang render audio + tạo {n_img} ảnh (Lightning)..."}
    tts_wavs, _ = await asyncio.gather(
        _run_tts_all(sentences, instruct),
        _run_image_gen_remote(image_prompts, session_id),
    )
    log.info("[VideoPipeline] TTS + image gen done in %.2fs", time.perf_counter() - t0)

    # Phase 4: Compute timings
    sentence_timings = compute_sentence_timings(tts_wavs)
    image_timings    = map_image_timings(image_prompts, sentence_timings)
    full_audio       = concat_wavs(tts_wavs)
    total_dur        = sentence_timings[-1][1] if sentence_timings else 0
    log.info("[VideoPipeline] total audio: %.1fs", total_dur)

    # Save session state — dùng để retry nếu render lỗi
    _save_session(session_id, topic, sentences, sentence_timings, image_timings, n_img)

    # Phase 5: Unload SD model to free VRAM before render
    yield {"type": "status", "data": "Giải phóng VRAM GPU..."}
    await remote_gen.unload()

    # Phase 6: Remotion render on Lightning
    yield {"type": "status", "data": "Đang render video trên Lightning (Remotion)..."}
    video_bytes = await remote_gen.render_video(
        session_id=session_id,
        n_images=n_img,
        image_timings=image_timings,
        sentences=sentences,
        sentence_timings=sentence_timings,
        audio_bytes=full_audio,
    )

    log.info("[VideoPipeline] DONE topic=%r total=%.2fs video=%d bytes",
             topic, time.perf_counter() - t0, len(video_bytes))
    yield {"type": "video_done", "video": video_bytes}
    _delete_session(session_id)


# ── Session persistence ───────────────────────────────────────────────────────

_SESSIONS_DIR = Path("app/data/sessions")


def _save_session(
    session_id: str,
    topic: str,
    sentences: list[str],
    sentence_timings: list[tuple[float, float]],
    image_timings: list[tuple[float, float]],
    n_images: int,
) -> None:
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "session_id": session_id,
        "topic": topic,
        "n_images": n_images,
        "sentences": sentences,
        "sentence_timings": [list(t) for t in sentence_timings],
        "image_timings": [list(t) for t in image_timings],
    }
    (_SESSIONS_DIR / f"{session_id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("[VideoPipeline] session saved → app/data/sessions/%s.json", session_id)


def _delete_session(session_id: str) -> None:
    p = _SESSIONS_DIR / f"{session_id}.json"
    p.unlink(missing_ok=True)


async def retry_render(session_id: str, audio_bytes: bytes) -> bytes:
    """Retry Remotion render từ session đã lưu — không cần gen lại TTS/ảnh."""
    path = _SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Session {session_id} không tìm thấy")
    data = json.loads(path.read_text(encoding="utf-8"))
    log.info("[VideoPipeline] Retry render session=%s topic=%r", session_id, data["topic"])
    return await remote_gen.render_video(
        session_id=data["session_id"],
        n_images=data["n_images"],
        image_timings=[tuple(t) for t in data["image_timings"]],
        sentences=data["sentences"],
        sentence_timings=[tuple(t) for t in data["sentence_timings"]],
        audio_bytes=audio_bytes,
    )


async def _local_render_flow(sentences, image_prompts, n_img, instruct, t0, topic):
    """Local flow: image bytes in memory → ffmpeg assembly."""
    # Phase 3: TTS + image gen in parallel
    yield {"type": "status", "data": f"Đang render audio + tạo {n_img} ảnh song song..."}
    tts_wavs, images_data = await asyncio.gather(
        _run_tts_all(sentences, instruct),
        _run_image_gen_local(image_prompts),
    )
    log.info("[VideoPipeline] TTS + image gen done in %.2fs", time.perf_counter() - t0)

    # Phase 4: Compute timing
    sentence_timings = compute_sentence_timings(tts_wavs)
    image_timings    = map_image_timings(image_prompts, sentence_timings)
    total_dur        = sentence_timings[-1][1] if sentence_timings else 0
    log.info("[VideoPipeline] total audio: %.1fs", total_dur)

    # Phase 5: Full audio + SRT
    full_audio = concat_wavs(tts_wavs)
    srt_text   = generate_srt(sentences, sentence_timings)

    # Phase 6: ffmpeg assembly
    yield {"type": "status", "data": "Đang ghép video (ffmpeg)..."}
    video_bytes = await assemble_video(
        image_data    = images_data,
        image_timings = image_timings,
        audio_bytes   = full_audio,
        srt_text      = srt_text,
        bg_music_path = BG_MUSIC_PATH,
    )

    log.info("[VideoPipeline] DONE topic=%r total=%.2fs video=%d bytes",
             topic, time.perf_counter() - t0, len(video_bytes))
    yield {"type": "video_done", "video": video_bytes}
