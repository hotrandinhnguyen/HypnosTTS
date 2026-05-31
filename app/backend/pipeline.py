import asyncio
import logging
import re
import time
from typing import AsyncIterator
from concurrent.futures import ThreadPoolExecutor

from app.backend.config import REF_AUDIO_PATH, REF_TEXT_PATH, TTS_NUM_STEPS, TTS_INSTRUCT
from app.backend.graph import build_graph
import app.backend.tts_engine as tts_engine

log = logging.getLogger("pipeline")

_executor = ThreadPoolExecutor(max_workers=1)
_graph = build_graph()

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[^\s])|(?<=\.)\s*\n+")


def _ref_text() -> str:
    if REF_TEXT_PATH.exists():
        return REF_TEXT_PATH.read_text(encoding="utf-8").strip()
    return ""


async def _synthesize_async(text: str, instruct: str) -> bytes:
    loop = asyncio.get_event_loop()
    t0 = time.perf_counter()
    result = await loop.run_in_executor(
        _executor,
        lambda: tts_engine.synthesize(
            text, str(REF_AUDIO_PATH), _ref_text(), instruct, TTS_NUM_STEPS
        ),
    )
    log.info("TTS [%.2fs] %r", time.perf_counter() - t0, text[:60])
    return result


def _status_message(event: dict) -> str:
    status = event.get("status", "")
    if status == "researched":
        return "Đang tạo phép ẩn dụ..."
    if status == "analogy_done":
        return "Đang viết bài giảng..."
    if status == "written" and event.get("revision_count", 0) > 0:
        return f"Đang kiểm tra và tinh chỉnh (lần {event['revision_count']})..."
    if status == "reviewed":
        review = event.get("review") or {}
        if not review.get("passed") and event.get("revision_count", 0) < 2:
            return "Đang viết lại để cải thiện..."
    return ""


def _split_sentences(script: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split(script)
    sentences: list[str] = []
    for part in parts:
        part = part.strip()
        if len(part) >= 4:
            sentences.append(part)
    return sentences


async def run(topic: str, instruct: str = TTS_INSTRUCT) -> AsyncIterator[dict]:
    t_total = time.perf_counter()

    # ── Phase 1: Run full graph (Researcher → Analogy → Writer → Reviewer loop) ──
    yield {"type": "status", "data": "Đang nghiên cứu chủ đề..."}
    log.info("[PIPELINE] START topic=%r", topic)

    initial_state = {
        "topic": topic,
        "instruct": instruct,
        "target_minutes": 0,
        "target_words": 0,
        "research": None,
        "analogy": None,
        "script": None,
        "review": None,
        "revision_count": 0,
        "status": "",
    }

    state = None
    async for event in _graph.astream(initial_state, stream_mode="values"):
        msg = _status_message(event)
        if msg:
            yield {"type": "status", "data": msg}
        state = event

    if not state or not state.get("script"):
        log.error("[PIPELINE] No script generated")
        yield {"type": "error", "data": "Không tạo được nội dung."}
        return

    script = state["script"]
    log.info("[PIPELINE] Graph done in %.2fs — script: %d chars", time.perf_counter() - t_total, len(script))

    review = state.get("review") or {}
    issues = review.get("issues", [])
    if issues:
        log.info("[PIPELINE] Reviewer issues (accepted anyway): %s", issues)

    # ── Phase 2: Stream sentences to TTS ─────────────────────────────────────────
    yield {"type": "status", "data": "Đang render giọng đọc..."}
    sentences = _split_sentences(script)
    log.info("[TTS] Streaming %d sentences", len(sentences))

    for i, sentence in enumerate(sentences, 1):
        log.info("[TTS] rendering #%d/%d...", i, len(sentences))
        audio = await _synthesize_async(sentence, instruct)
        yield {"type": "text", "data": sentence, "audio": audio}

    log.info("=== DONE topic=%r total=%.2fs ===", topic, time.perf_counter() - t_total)
    yield {"type": "done"}
