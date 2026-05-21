import asyncio
import logging
import time
from typing import AsyncIterator
from concurrent.futures import ThreadPoolExecutor

from app.backend.config import REF_AUDIO_PATH, REF_TEXT_PATH, TTS_NUM_STEPS, TTS_INSTRUCT
from app.backend.schemas import EnrichedOutline
from app.backend.agents.planner import planner_node
from app.backend.agents.researcher import researcher_node
from app.backend.agents.writer import write
import app.backend.tts_engine as tts_engine

log = logging.getLogger("pipeline")

_executor = ThreadPoolExecutor(max_workers=1)


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


async def _writer_producer(
    outline: EnrichedOutline,
    sentence_queue: "asyncio.Queue[str | None]",
):
    count = 0
    async for sentence in write(outline):
        count += 1
        log.debug("[WRITER] #%d %r", count, sentence[:80])
        await sentence_queue.put(sentence)
    log.info("[WRITER] finished, %d sentences", count)
    await sentence_queue.put(None)


async def _tts_consumer(
    sentence_queue: "asyncio.Queue[str | None]",
    out_queue: "asyncio.Queue[dict | None]",
    instruct: str,
):
    idx = 0
    while True:
        sentence = await sentence_queue.get()
        if sentence is None:
            break
        idx += 1
        log.info("[TTS] rendering #%d...", idx)
        audio = await _synthesize_async(sentence, instruct)
        log.info("[TTS] #%d done (%d bytes)", idx, len(audio))
        await out_queue.put({"type": "text", "data": sentence, "audio": audio})
    await out_queue.put(None)


async def run(topic: str, instruct: str = TTS_INSTRUCT) -> AsyncIterator[dict]:
    t_total = time.perf_counter()

    # ── Phase 1: Planner ─────────────────────────────────────────────────────
    yield {"type": "status", "data": "Planner đang phân tích chủ đề..."}
    log.info("[PLANNER] START topic=%r", topic)
    t0 = time.perf_counter()
    state = {"topic": topic, "outline": None, "enriched_outline": None, "status": ""}
    planner_out = await planner_node(state)
    log.info("[PLANNER] DONE (%.2fs)", time.perf_counter() - t0)

    # ── Phase 2: Researcher ───────────────────────────────────────────────────
    yield {"type": "status", "data": "Researcher đang làm phong phú khái niệm..."}
    log.info("[RESEARCHER] START")
    t0 = time.perf_counter()
    researcher_out = await researcher_node({**state, **planner_out})
    log.info("[RESEARCHER] DONE (%.2fs)", time.perf_counter() - t0)

    enriched = EnrichedOutline(**researcher_out["enriched_outline"])

    # ── Phase 3: Writer + TTS song song ──────────────────────────────────────
    yield {"type": "status", "data": "Writer đang viết — TTS đang render từng câu..."}
    log.info("[WRITER+TTS] START concurrent | instruct=%r", instruct)

    sentence_queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=4)
    out_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    producer = asyncio.create_task(_writer_producer(enriched, sentence_queue))
    consumer = asyncio.create_task(_tts_consumer(sentence_queue, out_queue, instruct))

    while True:
        item = await out_queue.get()
        if item is None:
            break
        yield item

    await producer
    await consumer

    log.info("=== DONE topic=%r total=%.2fs ===", topic, time.perf_counter() - t_total)
    yield {"type": "done"}
