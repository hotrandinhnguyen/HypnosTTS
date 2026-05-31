"""Two-step image prompt generation for video chunks."""
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.backend.config import OPENAI_API_KEY, OPENAI_MODEL
from app.backend.prompts import CHUNK_ANALYZER_SYSTEM, VISUAL_PROMPTER_SYSTEM
from app.backend.schemas import ChunkAnalysis, ChunkAnalysisList, ChunkPrompt, ChunkPromptList

log = logging.getLogger("image_prompter")

_llm_analyzer = ChatOpenAI(
    model=OPENAI_MODEL, temperature=0.3, api_key=OPENAI_API_KEY,
).with_structured_output(ChunkAnalysisList)

_llm_prompter = ChatOpenAI(
    model=OPENAI_MODEL, temperature=0.6, api_key=OPENAI_API_KEY,
).with_structured_output(ChunkPromptList)


def _target_chunks(total_duration: float) -> int:
    """Fallback target when caller did not pass an explicit image count."""
    return max(4, min(80, int(total_duration / 10)))


def _even_starts(n_sentences: int, target: int) -> list[int]:
    if target <= 1 or n_sentences <= 1:
        return [0]
    return sorted({
        min(n_sentences - 1, round(i * (n_sentences - 1) / (target - 1)))
        for i in range(target)
    })


def _fallback_analysis(topic: str, start: int) -> ChunkAnalysis:
    return ChunkAnalysis(
        start=start,
        concept=f"{topic} segment",
        metaphor="",
        visual_core=f"A clear visual explanation of {topic} at this point in the lesson",
        mood="analytical",
    )


def _normalize_chunks(
    chunks: list[ChunkAnalysis],
    target: int,
    n_sentences: int,
    topic: str,
) -> list[ChunkAnalysis]:
    if n_sentences <= 0:
        return []

    target = max(1, min(target, n_sentences))
    by_start: dict[int, ChunkAnalysis] = {}
    for chunk in sorted(chunks, key=lambda c: c.start):
        if 0 <= chunk.start < n_sentences and chunk.start not in by_start:
            by_start[chunk.start] = chunk

    by_start.setdefault(0, _fallback_analysis(topic, 0))

    for start in _even_starts(n_sentences, target):
        if len(by_start) >= target:
            break
        by_start.setdefault(start, _fallback_analysis(topic, start))

    normalized = sorted(by_start.values(), key=lambda c: c.start)
    if len(normalized) > target:
        step = len(normalized) / target
        keep = sorted({0} | {round(i * step) for i in range(1, target)})
        normalized = [normalized[i] for i in keep if i < len(normalized)]

    return normalized


def _fallback_prompt(topic: str, chunk: ChunkAnalysis) -> str:
    core = chunk.visual_core or chunk.concept or topic
    return (
        f"{core}, grounded in the domain of {topic}, cinematic educational visual, "
        "medium shot, clean composition, realistic lighting, highly detailed, sharp focus, 4k"
    )


async def generate_image_prompts(
    sentences: list[str],
    topic: str,
    total_duration: float = 0.0,
    n_images: int = 0,
) -> list[dict]:
    """
    Return {sentence_index, prompt} entries. The final count is normalized to
    the requested target, capped by the number of available sentences.
    """
    n = len(sentences)
    if n == 0:
        return []

    if n_images > 0:
        target = n_images
    elif total_duration > 0:
        target = _target_chunks(total_duration)
    else:
        target = 45
    target = max(1, min(target, n))

    numbered = "\n".join(f"[{i}] {s}" for i, s in enumerate(sentences))
    log.info("[ImagePrompter/Analyzer] analyzing %d sentences -> target %d chunks", n, target)

    analysis: ChunkAnalysisList = await _llm_analyzer.ainvoke([
        SystemMessage(content=CHUNK_ANALYZER_SYSTEM),
        HumanMessage(
            content=(
                f"Topic: {topic}\n"
                f"Total sentences: {n}\n"
                f"Target chunks: {target}\n\n"
                f"Script:\n{numbered}"
            )
        ),
    ])

    chunks = _normalize_chunks(analysis.chunks, target, n, topic)
    log.info("[ImagePrompter/Analyzer] %d chunks analyzed", len(chunks))

    chunks_text = "\n".join(
        f"[{c.start}] concept={c.concept!r} | metaphor={c.metaphor!r} | "
        f"visual_core={c.visual_core!r} | mood={c.mood}"
        for c in chunks
    )
    human = (
        f"TOPIC (anchor all images to this domain): {topic}\n"
        f"Total chunks: {len(chunks)}\n\n"
        f"Analyzed chunks:\n{chunks_text}"
    )

    log.info("[ImagePrompter/Prompter] generating %d prompts", len(chunks))
    result: ChunkPromptList = await _llm_prompter.ainvoke([
        SystemMessage(content=VISUAL_PROMPTER_SYSTEM),
        HumanMessage(content=human),
    ])

    chunk_starts = {c.start for c in chunks}
    prompt_by_start: dict[int, ChunkPrompt] = {}
    for prompt in sorted(result.chunks, key=lambda p: p.start):
        if prompt.start in chunk_starts and prompt.start not in prompt_by_start:
            prompt_by_start[prompt.start] = prompt

    prompts = [
        prompt_by_start.get(c.start) or ChunkPrompt(start=c.start, prompt=_fallback_prompt(topic, c))
        for c in chunks
    ]

    log.info("[ImagePrompter] done -> %d prompts (target=%d)", len(prompts), target)
    return [{"sentence_index": p.start, "prompt": p.prompt} for p in prompts]
