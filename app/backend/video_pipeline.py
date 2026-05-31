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
    assemble_video_from_clips,
)

log = logging.getLogger("video_pipeline")

_graph    = build_graph()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-tts")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[^\s])|(?<=\.)\s*\n+")
_WORD_SPLIT = re.compile(r"\S+")
_DEFAULT_IMAGE_SECONDS = 12
_I2V_IMAGE_SECONDS = 5
# Measured locally with OmniVoice/TTS_INSTRUCT on 2026-05-30:
# 105 Vietnamese words -> 28.04s audio, average 3.74 words/s.
_MEASURED_TTS_WORDS_PER_SECOND = 3.74


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ref_text() -> str:
    if REF_TEXT_PATH.exists():
        return REF_TEXT_PATH.read_text(encoding="utf-8").strip()
    return ""


def _split_sentences(script: str) -> list[str]:
    return [p.strip() for p in _SENTENCE_SPLIT.split(script) if len(p.strip()) >= 4]


def _auto_image_count(duration_seconds: int, video_mode: str) -> int:
    image_seconds = _I2V_IMAGE_SECONDS if video_mode == "i2v" else _DEFAULT_IMAGE_SECONDS
    return max(4, min(80, round(duration_seconds / image_seconds)))


def _word_count(text: str) -> int:
    return len(_WORD_SPLIT.findall(text))


def _planned_target_words(duration_minutes: int) -> int:
    return max(80, round(_MEASURED_TTS_WORDS_PER_SECOND * duration_minutes * 60))


def _estimate_tts_seconds(text: str) -> float:
    return max(1.0, _word_count(text) / _MEASURED_TTS_WORDS_PER_SECOND)


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


def _log_timing_summary(label: str, timings: list[tuple[float, float]]) -> None:
    if not timings:
        log.info("%s no timings", label)
        return
    durations = [max(e - s, 0.0) for s, e in timings]
    log.info(
        "%s count=%d total=%.2fs min=%.2fs max=%.2fs avg=%.2fs first=%s",
        label,
        len(timings),
        sum(durations),
        min(durations),
        max(durations),
        sum(durations) / len(durations),
        [(round(s, 2), round(e, 2)) for s, e in timings[:5]],
    )


# ── TTS ───────────────────────────────────────────────────────────────────────

async def _run_tts_all(sentences: list[str], instruct: str) -> list[bytes]:
    results: list[bytes] = []
    t0 = time.perf_counter()
    for i, sent in enumerate(sentences, 1):
        sent_t0 = time.perf_counter()
        log.info("[Video/TTS] start %d/%d chars=%d", i, len(sentences), len(sent))
        wav = await _synthesize_one(sent, instruct)
        dur = compute_sentence_timings([wav])[0][1]
        log.info(
            "[Video/TTS] done %d/%d runtime=%.2fs audio=%.2fs bytes=%d text=%r",
            i,
            len(sentences),
            time.perf_counter() - sent_t0,
            dur,
            len(wav),
            sent[:80],
        )
        results.append(wav)
    log.info("[Video/TTS] all done count=%d runtime=%.2fs", len(sentences), time.perf_counter() - t0)
    return results


# ── Image gen (local ffmpeg path) ─────────────────────────────────────────────

async def _run_image_gen_local(image_prompts: list[dict]) -> list[bytes]:
    images: list[bytes] = []
    t0 = time.perf_counter()
    for i, p in enumerate(image_prompts):
        img_t0 = time.perf_counter()
        png = await generate_image(p["prompt"])
        log.info(
            "[Video/ImgGenLocal] done %d/%d runtime=%.2fs bytes=%d sentence_index=%s",
            i + 1,
            len(image_prompts),
            time.perf_counter() - img_t0,
            len(png),
            p.get("sentence_index"),
        )
        images.append(png)
    log.info("[Video/ImgGenLocal] all done count=%d runtime=%.2fs", len(images), time.perf_counter() - t0)
    return images


# ── Image gen (remote path — saves to Lightning disk) ─────────────────────────

async def _run_image_gen_remote(image_prompts: list[dict], session_id: str) -> None:
    t0 = time.perf_counter()
    for i, p in enumerate(image_prompts):
        img_t0 = time.perf_counter()
        await remote_gen.generate_save(p["prompt"], session_id, i)
        log.info(
            "[Video/ImgGenRemote] done %d/%d runtime=%.2fs session=%s sentence_index=%s",
            i + 1,
            len(image_prompts),
            time.perf_counter() - img_t0,
            session_id,
            p.get("sentence_index"),
        )
    log.info("[Video/ImgGenRemote] all done count=%d runtime=%.2fs session=%s", len(image_prompts), time.perf_counter() - t0, session_id)


# ── Main entry ────────────────────────────────────────────────────────────────

async def run_video(topic: str, instruct: str = TTS_INSTRUCT, n_images: int = 0, duration_minutes: int = 0, video_mode: str = "i2v") -> AsyncIterator[dict]:
    """
    Yields:
      {"type": "status",     "data": str}    — progress messages
      {"type": "video_done", "video": bytes}  — final MP4 bytes
      {"type": "error",      "data": str}     — on failure
    """
    t0 = time.perf_counter()
    if video_mode != "i2v":
        log.info("[VideoPipeline] Remotion slideshow disabled; forcing i2v instead of %s", video_mode)
        video_mode = "i2v"
    log.info("[VideoPipeline] START topic=%r provider=%s", topic, IMAGE_PROVIDER)

    target_words = 0
    if duration_minutes > 0:
        target_words = _planned_target_words(duration_minutes)
        log.info(
            "[VideoPipeline] plan duration=%dmin target_words=%d wps=%.2f mode=%s",
            duration_minutes,
            target_words,
            _MEASURED_TTS_WORDS_PER_SECOND,
            video_mode,
        )
        yield {
            "type": "status",
            "data": (
                f"Kế hoạch nội dung: khoảng {target_words} từ "
                f"cho {duration_minutes} phút."
            ),
        }

    # ── Phase 1: LangGraph ───────────────────────────────────────────────────
    yield {"type": "status", "data": "Đang nghiên cứu chủ đề..."}

    initial_state = {
        "topic": topic, "instruct": instruct,
        "target_minutes": duration_minutes,
        "target_words": target_words,
        "research": None, "analogy": None,
        "script": None, "review": None,
        "revision_count": 0, "status": "",
    }

    state = None
    graph_t0 = time.perf_counter()
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
    log.info(
        "[VideoPipeline] graph done phase=graph runtime=%.2fs total=%.2fs sentences=%d words=%d chars=%d",
        time.perf_counter() - graph_t0,
        time.perf_counter() - t0,
        len(sentences),
        _word_count(script),
        len(script),
    )

    # ── Phase 2: Image prompt generation ────────────────────────────────────
    estimated_duration = _estimate_tts_seconds(script)
    planned_n_images = n_images
    if planned_n_images <= 0:
        planned_n_images = _auto_image_count(round(estimated_duration), video_mode)
    log.info(
        "[VideoPipeline] script estimate words=%d duration=%.1fs images=%d user_images=%d",
        _word_count(script),
        estimated_duration,
        planned_n_images,
        n_images,
    )
    yield {
        "type": "status",
        "data": (
            f"Kịch bản {len(sentences)} câu, ước lượng {estimated_duration:.0f}s. "
            f"Đang tạo {planned_n_images} prompt ảnh..."
        ),
    }
    prompt_t0 = time.perf_counter()
    image_prompts = await generate_image_prompts(
        sentences,
        topic,
        total_duration=estimated_duration,
        n_images=planned_n_images,
    )
    n_img = len(image_prompts)
    log.info(
        "[VideoPipeline] prompts done runtime=%.2fs count=%d starts=%s",
        time.perf_counter() - prompt_t0,
        n_img,
        [p.get("sentence_index") for p in image_prompts[:20]],
    )

    # ── Phase 3–6: branch on video_mode / IMAGE_PROVIDER ─────────────────────
    if video_mode == "i2v":
        async for event in _i2v_render_flow(
            sentences, image_prompts, n_img, instruct, t0, topic
        ):
            yield event
    elif IMAGE_PROVIDER == "remote":
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

    log.info("[VideoPipeline/Remote] DONE topic=%r total=%.2fs video=%d bytes",
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

    log.info("[VideoPipeline/Local] DONE topic=%r total=%.2fs video=%d bytes",
             topic, time.perf_counter() - t0, len(video_bytes))
    yield {"type": "video_done", "video": video_bytes}


async def _i2v_render_flow(sentences, image_prompts, n_img, instruct, t0, topic):
    """I2V flow: SD images saved to Lightning → Wan I2V clips → ffmpeg assembly."""
    session_id = uuid.uuid4().hex[:8]

    # Phase 3: TTS (local) + image gen (Lightning) in parallel
    yield {"type": "status", "data": f"Đang render audio + tạo {n_img} ảnh..."}
    parallel_t0 = time.perf_counter()
    tts_wavs, _ = await asyncio.gather(
        _run_tts_all(sentences, instruct),
        _run_image_gen_remote(image_prompts, session_id),
    )
    log.info("[VideoPipeline/I2V] phase=tts+images runtime=%.2fs total=%.2fs", time.perf_counter() - parallel_t0, time.perf_counter() - t0)

    # Phase 4: Compute timings
    sentence_timings = compute_sentence_timings(tts_wavs)
    image_timings    = map_image_timings(image_prompts, sentence_timings)
    full_audio       = concat_wavs(tts_wavs)
    srt_text         = generate_srt(sentences, sentence_timings)
    _log_timing_summary("[VideoPipeline/I2V] sentence_timings", sentence_timings)
    _log_timing_summary("[VideoPipeline/I2V] image_timings", image_timings)
    log.info("[VideoPipeline/I2V] full_audio bytes=%d srt_chars=%d", len(full_audio), len(srt_text))

    # Phase 5: Unload SD, generate I2V clips sequentially
    yield {"type": "status", "data": "Giải phóng VRAM SD, bắt đầu I2V..."}
    unload_t0 = time.perf_counter()
    await remote_gen.unload()
    log.info("[VideoPipeline/I2V] phase=unload runtime=%.2fs", time.perf_counter() - unload_t0)

    clips: list[bytes] = []
    i2v_t0 = time.perf_counter()
    for i, (start_t, end_t) in enumerate(image_timings):
        duration_s = max(end_t - start_t, 1.5)
        prompt = image_prompts[i].get("prompt", "")
        yield {"type": "status", "data": f"I2V clip {i + 1}/{n_img} ({duration_s:.1f}s)..."}
        clip_t0 = time.perf_counter()
        clip = await remote_gen.generate_clip(session_id, i, duration_s, prompt)
        clips.append(clip)
        log.info(
            "[VideoPipeline/I2V] clip %d/%d done runtime=%.2fs timeline=(%.2f, %.2f) dur=%.2fs bytes=%d",
            i + 1,
            n_img,
            time.perf_counter() - clip_t0,
            start_t,
            end_t,
            duration_s,
            len(clip),
        )
    log.info("[VideoPipeline/I2V] phase=i2v_clips runtime=%.2fs clips=%d bytes=%d", time.perf_counter() - i2v_t0, len(clips), sum(len(c) for c in clips))

    # Phase 6: ffmpeg assembly
    yield {"type": "status", "data": "Đang ghép video (ffmpeg)..."}
    assemble_t0 = time.perf_counter()
    video_bytes = await assemble_video_from_clips(
        clip_data     = clips,
        audio_bytes   = full_audio,
        srt_text      = srt_text,
        bg_music_path = BG_MUSIC_PATH,
    )
    log.info("[VideoPipeline/I2V] phase=assemble runtime=%.2fs", time.perf_counter() - assemble_t0)

    log.info("[VideoPipeline/I2V] DONE topic=%r total=%.2fs video=%d bytes",
             topic, time.perf_counter() - t0, len(video_bytes))
    yield {"type": "video_done", "video": video_bytes}
