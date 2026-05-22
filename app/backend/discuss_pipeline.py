"""Discussion pipeline — AI answers questions about a lesson using the script as context."""
import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.backend.config import (
    OPENAI_API_KEY, OPENAI_MODEL,
    REF_AUDIO_PATH, REF_TEXT_PATH, TTS_NUM_STEPS, TTS_INSTRUCT,
)
import app.backend.tts_engine as tts_engine

log = logging.getLogger("discuss_pipeline")

_llm      = ChatOpenAI(model=OPENAI_MODEL, temperature=0.7, api_key=OPENAI_API_KEY)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="discuss-tts")

_SENT_RE = re.compile(r"(?<=[.!?…])\s+(?=[^\s])")

DISCUSS_SYSTEM = """\
Bạn là trợ lý giáo dục thông minh. Bạn vừa dạy người học một bài giảng podcast chi tiết.
Người học đang đặt câu hỏi — hãy trả lời dựa trên nội dung bài giảng đó.

QUY TẮC TRẢ LỜI:
- Tối đa 120 từ — ngắn gọn, đi thẳng vào vấn đề
- Viết dạng NÓI: câu ngắn, tự nhiên, không markdown, không bullet list, không tiêu đề
- Ưu tiên ví dụ và ẩn dụ từ chính bài giảng khi giải thích lại
- Nếu câu hỏi ngoài bài giảng → trả lời ngắn rồi kéo về chủ đề
- Tông giọng: thân thiện, như người thầy đang giải đáp trực tiếp"""


def _split(text: str) -> list[str]:
    return [s.strip() for s in _SENT_RE.split(text) if len(s.strip()) >= 4]


async def _tts(text: str, instruct: str) -> bytes:
    ref = REF_TEXT_PATH.read_text(encoding="utf-8").strip() if REF_TEXT_PATH.exists() else ""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: tts_engine.synthesize(text, str(REF_AUDIO_PATH), ref, instruct, TTS_NUM_STEPS),
    )


async def run_discuss(
    script: str,
    history: list[dict],      # [{"role": "user"|"ai", "text": str}]
    question: str,
    instruct: str = TTS_INSTRUCT,
) -> AsyncIterator[dict]:
    """
    Yields:
      {"type": "text", "data": sentence, "audio": wav_bytes}  — per sentence
      {"type": "done", "full_text": str}                       — final
      {"type": "error", "data": str}                           — on failure
    """
    messages: list = [SystemMessage(content=DISCUSS_SYSTEM)]
    messages.append(HumanMessage(content=f"Bài giảng tôi vừa dạy:\n{script[:4000]}"))

    # Last 3 exchanges of history
    for turn in history[-6:]:
        if turn.get("role") == "user":
            messages.append(HumanMessage(content=turn["text"]))
        else:
            messages.append(AIMessage(content=turn["text"]))

    messages.append(HumanMessage(content=question))

    log.info("[Discuss] question=%r history_turns=%d", question[:80], len(history))

    try:
        response = await _llm.ainvoke(messages)
        answer = response.content.strip()
    except Exception as e:
        log.exception("[Discuss] LLM error: %s", e)
        yield {"type": "error", "data": str(e)}
        return

    log.info("[Discuss] answer=%d chars", len(answer))

    sentences = _split(answer) or [answer]
    for sent in sentences:
        try:
            wav = await _tts(sent, instruct)
            yield {"type": "text", "data": sent, "audio": wav}
        except Exception as e:
            log.warning("[Discuss] TTS failed for %r: %s", sent[:40], e)

    yield {"type": "done", "full_text": answer}
