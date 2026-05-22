import asyncio
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.backend.config import OPENAI_API_KEY, OPENAI_MODEL
from app.backend.schemas import SearchQueries, ResearchData
from app.backend.prompts import RESEARCHER_QUERIES_SYSTEM, RESEARCHER_EXTRACT_SYSTEM
from app.backend.state import GraphState
from app.backend.tools.web_search import search
from app.backend.db import get_cached_research, save_research_cache

log = logging.getLogger("researcher")

_llm_queries = ChatOpenAI(
    model=OPENAI_MODEL, temperature=0.3, api_key=OPENAI_API_KEY,
).with_structured_output(SearchQueries)

_llm_extract = ChatOpenAI(
    model=OPENAI_MODEL, temperature=0.2, api_key=OPENAI_API_KEY,
).with_structured_output(ResearchData)

MAX_SEARCHES = 3


async def _generate_queries(topic: str) -> list[str]:
    result: SearchQueries = await _llm_queries.ainvoke([
        SystemMessage(content=RESEARCHER_QUERIES_SYSTEM),
        HumanMessage(content=f"Khái niệm/chủ đề cần nghiên cứu: {topic}"),
    ])
    return result.queries[:MAX_SEARCHES]


async def _run_searches(queries: list[str]) -> str:
    results_lists = await asyncio.gather(*[search(q, timeout=5.0) for q in queries])
    snippets: list[str] = []
    for query, results in zip(queries, results_lists):
        snippets.append(f"[Query: {query}]")
        for r in results:
            if r["body"]:
                snippets.append(f"• {r['title']}: {r['body'][:300]}")
    return "\n".join(snippets)


async def _extract_research(topic: str, raw_text: str) -> ResearchData:
    prompt = (
        f"Chủ đề: {topic}\n\n"
        f"Dữ liệu từ web:\n{raw_text[:4000]}\n\n"
        "Trích xuất thông tin chất lượng cao, trả về JSON đúng schema."
    )
    return await _llm_extract.ainvoke([
        SystemMessage(content=RESEARCHER_EXTRACT_SYSTEM),
        HumanMessage(content=prompt),
    ])


async def researcher_node(state: GraphState) -> dict:
    topic = state["topic"]
    log.info("[Researcher] START topic=%r", topic)

    cached = await get_cached_research(topic)
    if cached:
        log.info("[Researcher] cache hit for %r", topic)
        return {"research": cached, "status": "researched"}

    queries = await _generate_queries(topic)
    log.info("[Researcher] queries: %s", queries)

    raw_text = await _run_searches(queries)
    if not raw_text.strip():
        log.warning("[Researcher] no search results, using topic name only")
        raw_text = f"Concept: {topic}"

    research: ResearchData = await _extract_research(topic, raw_text)
    data = research.model_dump()

    await save_research_cache(topic, data)
    log.info("[Researcher] DONE — %d facts, %d mechanisms", len(data["key_facts"]), len(data["mechanisms"]))
    return {"research": data, "status": "researched"}
