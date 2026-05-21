import re
from typing import AsyncIterator
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.backend.config import OPENAI_API_KEY, OPENAI_MODEL
from app.backend.schemas import EnrichedOutline
from app.backend.prompts import WRITER_FULL_PROMPT

_llm = ChatOpenAI(
    model=OPENAI_MODEL,
    temperature=0.85,
    api_key=OPENAI_API_KEY,
    streaming=True,
)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _build_full_prompt(outline: EnrichedOutline) -> str:
    sections: list[str] = []

    sections.append(
        f"PHẦN MỞ ĐẦU — hook hấp dẫn (3-5 câu):\n"
        f"  Gợi ý nội dung: {outline.intro}"
    )

    for i, c in enumerate(outline.concepts, 1):
        sections.append(
            f"KHÁI NIỆM {i} — {c.name} (6-9 câu):\n"
            f"  Định nghĩa: {c.definition}\n"
            f"  Tại sao quan trọng: {c.why_it_matters}\n"
            f"  Cơ chế hoạt động: {c.how_it_works}\n"
            f"  Ví dụ thực tế: {c.example}\n"
            f"  Sai lầm phổ biến: {c.misconception}\n"
            f"  Phép ẩn dụ: {c.analogy}\n"
            f"  Insight sâu hơn: {c.deeper_note}"
        )

    for d in outline.distinctions:
        a, b = d.pair[0], d.pair[1]
        sections.append(
            f"PHÂN BIỆT — {a} vs {b} (4-6 câu):\n"
            f"  Giải thích: {d.explanation}\n"
            f"  Bắt đầu bằng 'Nhiều người hay nhầm...' hoặc 'Điểm dễ nhầm nhất là...'\n"
            f"  Kết bằng một quy tắc ngón tay cái để phân biệt nhanh."
        )

    sections.append(
        f"PHẦN KẾT (3-5 câu):\n"
        f"  Nội dung tổng kết: {outline.summary}\n"
        f"  Nhắc lại ý lớn nhất, gợi ý bước tiếp theo, kết bằng câu truyền cảm hứng."
    )

    numbered = "\n\n".join(f"[{i+1}] {s}" for i, s in enumerate(sections))
    return WRITER_FULL_PROMPT.format(topic=outline.topic, sections=numbered)


async def write(outline: EnrichedOutline) -> AsyncIterator[str]:
    """Một LLM call duy nhất — stream toàn bộ script, yield từng câu hoàn chỉnh."""
    prompt = _build_full_prompt(outline)
    buf = ""
    async for chunk in _llm.astream([HumanMessage(content=prompt)]):
        buf += chunk.content
        parts = _SENTENCE_END.split(buf)
        for sentence in parts[:-1]:
            if sentence.strip():
                yield sentence.strip()
        buf = parts[-1]
    if buf.strip():
        yield buf.strip()
