from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.backend.config import OPENAI_API_KEY, OPENAI_MODEL
from app.backend.schemas import Outline
from app.backend.prompts import PLANNER_SYSTEM
from app.backend.state import GraphState

_llm = ChatOpenAI(
    model=OPENAI_MODEL,
    temperature=0.3,
    api_key=OPENAI_API_KEY,
).with_structured_output(Outline)


async def planner_node(state: GraphState) -> dict:
    outline: Outline = await _llm.ainvoke([
        SystemMessage(content=PLANNER_SYSTEM),
        HumanMessage(content=f"Chủ đề cần học: {state['topic']}"),
    ])
    return {"outline": outline.model_dump(), "status": "planned"}
