import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.backend.config import OPENAI_API_KEY, OPENAI_MODEL
from app.backend.prompts import (
    WRITER_SYSTEM, WRITER_REVISION_SYSTEM,
    writer_prompt, writer_revision_prompt,
)
from app.backend.state import GraphState

log = logging.getLogger("writer")

_llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0.85, api_key=OPENAI_API_KEY)


async def writer_node(state: GraphState) -> dict:
    topic = state["topic"]
    research = state.get("research") or {}
    analogy = state.get("analogy") or {}
    revision_count = state.get("revision_count", 0)
    existing_script = state.get("script")
    review = state.get("review")

    log.info("[Writer] START topic=%r revision=%d", topic, revision_count)

    if existing_script and review and not review.get("passed") and revision_count > 0:
        system = WRITER_REVISION_SYSTEM
        human_text = writer_revision_prompt(
            topic,
            existing_script,
            review.get("issues", []),
            review.get("suggestion", ""),
        )
    else:
        system = WRITER_SYSTEM
        human_text = writer_prompt(topic, research, analogy)

    response = await _llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=human_text),
    ])
    script = response.content.strip()
    log.info("[Writer] DONE — %d chars, revision=%d", len(script), revision_count)
    return {"script": script, "revision_count": revision_count, "status": "written"}
