"""Generate image prompts per semantic chunk — single API call, 15-25 chunks."""
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.backend.config import OPENAI_API_KEY, OPENAI_MODEL
from app.backend.schemas import ChunkPromptList
from app.backend.prompts import IMAGE_PROMPTER_SYSTEM

log = logging.getLogger("image_prompter")

_llm = ChatOpenAI(
    model=OPENAI_MODEL, temperature=0.4, api_key=OPENAI_API_KEY,
).with_structured_output(ChunkPromptList)

_FALLBACK = "Abstract glowing concept visualization with floating data elements, cinematic lighting, highly detailed, sharp focus, rich colors, dark background, 4k"


async def generate_image_prompts(sentences: list[str], topic: str) -> list[dict]:
    """
    Returns list of {sentence_index, prompt} — one per semantic chunk.
    Compatible with map_image_timings which uses sentence_index as start marker.
    """
    numbered = "\n".join(f"[{i}] {s}" for i, s in enumerate(sentences))
    human = (
        f"Topic: {topic}\n"
        f"Total sentences: {len(sentences)}\n\n"
        f"Script:\n{numbered[:10000]}"
    )

    log.info("[ImagePrompter] requesting semantic chunks for %d sentences", len(sentences))
    result: ChunkPromptList = await _llm.ainvoke([
        SystemMessage(content=IMAGE_PROMPTER_SYSTEM),
        HumanMessage(content=human),
    ])

    chunks = result.chunks
    n = len(sentences)

    # Validate + sort by start index
    chunks = [c for c in chunks if 0 <= c.start < n]
    chunks.sort(key=lambda c: c.start)

    # Ensure sentence 0 is always covered
    if not chunks or chunks[0].start != 0:
        chunks.insert(0, type(chunks[0])(start=0, prompt=_FALLBACK) if chunks else None)
        if chunks[0] is None:
            from app.backend.schemas import ChunkPrompt
            chunks[0] = ChunkPrompt(start=0, prompt=_FALLBACK)

    log.info("[ImagePrompter] %d chunks generated", len(chunks))
    return [{"sentence_index": c.start, "prompt": c.prompt} for c in chunks]
