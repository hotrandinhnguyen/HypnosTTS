"""Pipeline đọc truyện: sentences sẵn có → TTS stream."""
import asyncio
import logging
import time
from typing import AsyncIterator

from app.backend.config import TTS_INSTRUCT, TTS_NUM_STEPS, REF_AUDIO_PATH, REF_TEXT_PATH
from app.backend.pipeline import _executor   # dùng chung executor với learning pipeline
import app.backend.tts_engine as tts_engine

log = logging.getLogger("story_pipeline")


def _ref_text() -> str:
    if REF_TEXT_PATH.exists():
        return REF_TEXT_PATH.read_text(encoding="utf-8").strip()
    return ""


async def _tts(text: str, instruct: str) -> bytes:
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


async def run_story(
    sentences: list[str],
    instruct: str = TTS_INSTRUCT,
) -> AsyncIterator[dict]:
    """Yield {type, data, audio} cho từng câu, cuối cùng yield {type: done}."""
    for i, sentence in enumerate(sentences):
        log.info("[STORY] #%d / %d", i + 1, len(sentences))
        audio = await _tts(sentence, instruct)
        yield {"type": "text", "data": sentence, "audio": audio}
    yield {"type": "done"}
