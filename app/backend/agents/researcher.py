import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.backend.config import OPENAI_API_KEY, OPENAI_MODEL
from app.backend.schemas import Outline, Concept, EnrichedConcept, EnrichedOutline
from app.backend.prompts import RESEARCHER_SYSTEM
from app.backend.state import GraphState

_llm = ChatOpenAI(
    model=OPENAI_MODEL,
    temperature=0.4,
    api_key=OPENAI_API_KEY,
).with_structured_output(EnrichedConcept)


async def _enrich_one(topic: str, concept: Concept) -> EnrichedConcept:
    prompt = (
        f"Chủ đề tổng quát: {topic}\n"
        f"Khái niệm: {concept.name}\n"
        f"Định nghĩa: {concept.definition}\n"
        f"Tại sao quan trọng: {concept.why_it_matters}\n"
        f"Cơ chế hoạt động: {concept.how_it_works}\n"
        f"Ví dụ: {concept.example}\n"
        f"Hiểu lầm: {concept.misconception}\n\n"
        "Trả về JSON với đúng các trường: name, definition, why_it_matters, how_it_works, "
        "example, misconception, analogy, deeper_note."
    )
    return await _llm.ainvoke([
        SystemMessage(content=RESEARCHER_SYSTEM),
        HumanMessage(content=prompt),
    ])


async def researcher_node(state: GraphState) -> dict:
    outline = Outline(**state["outline"])
    enriched_concepts = await asyncio.gather(
        *[_enrich_one(outline.topic, c) for c in outline.concepts]
    )
    enriched = EnrichedOutline(
        topic=outline.topic,
        intro=outline.intro,
        concepts=list(enriched_concepts),
        distinctions=outline.distinctions,
        summary=outline.summary,
    )
    return {"enriched_outline": enriched.model_dump(), "status": "researched"}
