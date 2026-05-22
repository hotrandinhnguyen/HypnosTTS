import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.backend.config import OPENAI_API_KEY, OPENAI_MODEL
from app.backend.schemas import Analogy
from app.backend.prompts import ANALOGY_SYSTEM
from app.backend.state import GraphState

log = logging.getLogger("analogy")

_llm = ChatOpenAI(
    model=OPENAI_MODEL, temperature=0.7, api_key=OPENAI_API_KEY,
).with_structured_output(Analogy)


async def analogy_node(state: GraphState) -> dict:
    topic = state["topic"]
    research = state.get("research") or {}
    log.info("[Analogy] START topic=%r", topic)

    examples = research.get("examples", [])
    mechanisms = research.get("mechanisms", [])

    context = (
        f"Chủ đề: {topic}\n\n"
        f"Cơ chế hoạt động: {'; '.join(mechanisms[:3])}\n"
        f"Ví dụ đã có (KHÔNG lặp lại): {'; '.join(examples[:3])}\n\n"
        "Tạo 3 phép ẩn dụ theo đúng schema."
    )

    analogy: Analogy = await _llm.ainvoke([
        SystemMessage(content=ANALOGY_SYSTEM),
        HumanMessage(content=context),
    ])
    log.info("[Analogy] DONE")
    return {"analogy": analogy.model_dump(), "status": "analogy_done"}
