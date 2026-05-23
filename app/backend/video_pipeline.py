"""
Video generation pipeline:
  LangGraph (Researcher → Analogy → Writer → Reviewer)
  → image prompt generation (LLM)
  → image gen + TTS in parallel
  → ffmpeg assembly → MP4
"""
import asyncio
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterator

from app.backend.config import (
    REF_AUDIO_PATH, REF_TEXT_PATH, TTS_NUM_STEPS, TTS_INSTRUCT, BG_MUSIC_PATH,
)
from app.backend.graph import build_graph
import app.backend.tts_engine as tts_engine
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


# ── Parallel image gen + TTS ──────────────────────────────────────────────────

async def _run_tts_all(sentences: list[str], instruct: str) -> list[bytes]:
    """Synthesize all sentences sequentially (GPU serialized). Returns list of WAV bytes."""
    results: list[bytes] = []
    for i, sent in enumerate(sentences, 1):
        log.info("[Video/TTS] %d/%d", i, len(sentences))
        wav = await _synthesize_one(sent, instruct)
        results.append(wav)
    return results


async def _run_image_gen_all(image_prompts: list[dict]) -> list[bytes]:
    """Generate images sequentially to avoid VRAM contention with TTS model."""
    images: list[bytes] = []
    for i, p in enumerate(image_prompts):
        png = await generate_image(p["prompt"])
        log.info("[Video/ImgGen] %d/%d done", i + 1, len(image_prompts))
        images.append(png)
    return images


# ── Main entry ────────────────────────────────────────────────────────────────

async def run_video(topic: str, instruct: str = TTS_INSTRUCT) -> AsyncIterator[dict]:
    """
    Yields:
      {"type": "status", "data": str}           — progress messages
      {"type": "video_done", "video": bytes}     — final MP4 bytes
      {"type": "error",  "data": str}            — on failure
    """
    t0 = time.perf_counter()
    log.info("[VideoPipeline] START topic=%r", topic)

    # ── Phase 1: LangGraph ───────────────────────────────────────────────────
    yield {"type": "status", "data": "Đang nghiên cứu chủ đề..."}

    initial_state = {
        "topic": topic, "instruct": instruct,
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
    estimated_duration = len(sentences) * 5.5  # ~5.5s/sentence average
    yield {"type": "status", "data": f"Kịch bản {len(sentences)} câu. Đang tạo prompt ảnh..."}
    image_prompts = await generate_image_prompts(sentences, topic, total_duration=estimated_duration)
    n_img = len(image_prompts)
    log.info("[VideoPipeline] %d image prompts", n_img)

    # ── Phase 3: TTS (local) + Image gen (Lightning) song song ─────────────
    yield {"type": "status", "data": f"Đang render audio + tạo {n_img} ảnh song song..."}
    tts_wavs, images_data = await asyncio.gather(
        _run_tts_all(sentences, instruct),
        _run_image_gen_all(image_prompts),
    )
    log.info("[VideoPipeline] TTS + image gen done in %.2fs", time.perf_counter() - t0)

    # ── Phase 4: Compute timing ───────────────────────────────────────────────
    sentence_timings = compute_sentence_timings(tts_wavs)
    image_timings    = map_image_timings(image_prompts, sentence_timings)
    total_dur = sentence_timings[-1][1] if sentence_timings else 0
    log.info("[VideoPipeline] total audio: %.1fs", total_dur)

    # ── Phase 5: Full audio + SRT ────────────────────────────────────────────
    full_audio = concat_wavs(tts_wavs)
    srt_text   = generate_srt(sentences, sentence_timings)

    # ── Phase 6: ffmpeg assembly ─────────────────────────────────────────────
    yield {"type": "status", "data": "Đang ghép video..."}
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
