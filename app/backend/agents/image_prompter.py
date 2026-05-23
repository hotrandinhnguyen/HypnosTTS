"""
2-agent image prompt pipeline:
  Agent 1 (ChunkAnalyzer)  — understands Vietnamese content, extracts visual intent
  Agent 2 (VisualPrompter) — writes detailed, diverse English image prompts
"""
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.backend.config import OPENAI_API_KEY, OPENAI_MODEL
from app.backend.schemas import ChunkAnalysisList, ChunkPrompt, ChunkPromptList
from app.backend.prompts import CHUNK_ANALYZER_SYSTEM, VISUAL_PROMPTER_SYSTEM

log = logging.getLogger("image_prompter")

_llm_analyzer = ChatOpenAI(
    model=OPENAI_MODEL, temperature=0.3, api_key=OPENAI_API_KEY,
).with_structured_output(ChunkAnalysisList)

_llm_prompter = ChatOpenAI(
    model=OPENAI_MODEL, temperature=0.6, api_key=OPENAI_API_KEY,
).with_structured_output(ChunkPromptList)

_FALLBACK_PROMPT = (
    "A single glowing idea crystallizing from darkness into a sharp geometric form, "
    "tight close-up macro, cold blue studio backlight, cinematic 3D render, "
    "highly detailed, sharp focus, 4k"
)


def _target_chunks(total_duration: float) -> int:
    """1 image per 10s of audio, clamped to [20, 80]."""
    return max(20, min(80, int(total_duration / 10)))


async def generate_image_prompts(
    sentences: list[str],
    topic: str,
    total_duration: float = 0.0,
) -> list[dict]:
    """
    Returns list of {sentence_index, prompt} — one per visual chunk (~40-55).
    Uses 2 agents: ChunkAnalyzer → VisualPrompter.
    """
    numbered = "\n".join(f"[{i}] {s}" for i, s in enumerate(sentences))
    n = len(sentences)

    # ── Agent 1: ChunkAnalyzer ────────────────────────────────────────────────
    target = _target_chunks(total_duration) if total_duration > 0 else 45
    log.info("[ImagePrompter/Analyzer] analyzing %d sentences → target %d chunks", n, target)
    analysis: ChunkAnalysisList = await _llm_analyzer.ainvoke([
        SystemMessage(content=CHUNK_ANALYZER_SYSTEM),
        HumanMessage(content=f"Topic: {topic}\nTotal sentences: {n}\nTarget chunks: {target}\n\nScript:\n{numbered}"),
    ])

    chunks = analysis.chunks
    chunks = [c for c in chunks if 0 <= c.start < n]
    chunks.sort(key=lambda c: c.start)

    if not chunks or chunks[0].start != 0:
        from app.backend.schemas import ChunkAnalysis
        chunks.insert(0, ChunkAnalysis(
            start=0,
            concept=topic,
            metaphor="",
            visual_core=f"A visual introduction to the concept of {topic}",
            mood="curious",
        ))

    log.info("[ImagePrompter/Analyzer] %d chunks analyzed", len(chunks))

    # ── Agent 2: VisualPrompter ───────────────────────────────────────────────
    chunks_text = "\n".join(
        f"[{c.start}] concept={c.concept!r} | metaphor={c.metaphor!r} | "
        f"visual_core={c.visual_core!r} | mood={c.mood}"
        for c in chunks
    )
    human = (
        f"Topic: {topic}\n"
        f"Total chunks: {len(chunks)}\n\n"
        f"Analyzed chunks:\n{chunks_text}"
    )

    log.info("[ImagePrompter/Prompter] generating %d prompts", len(chunks))
    result: ChunkPromptList = await _llm_prompter.ainvoke([
        SystemMessage(content=VISUAL_PROMPTER_SYSTEM),
        HumanMessage(content=human),
    ])

    prompts = result.chunks
    prompts = [p for p in prompts if 0 <= p.start < n]
    prompts.sort(key=lambda p: p.start)

    # Ensure sentence 0 covered
    if not prompts or prompts[0].start != 0:
        prompts.insert(0, ChunkPrompt(start=0, prompt=_FALLBACK_PROMPT))

    log.info("[ImagePrompter] done — %d prompts", len(prompts))
    return [{"sentence_index": p.start, "prompt": p.prompt} for p in prompts]
