import asyncio
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.backend.config import OPENAI_API_KEY, OPENAI_MODEL
from app.backend.schemas import SearchQueries, ResearchData
from app.backend.prompts import (
    RESEARCHER_QUERIES_SYSTEM,
    RESEARCHER_EXTRACT_SYSTEM,
    SELF_RESEARCH_SYSTEM,
)
from app.backend.state import GraphState
from app.backend.tools.web_search import search
from app.backend.tools.wiki_search import fetch_summary
from app.backend.db import get_cached_research, save_research_cache

log = logging.getLogger("researcher")

_llm_queries = ChatOpenAI(
    model=OPENAI_MODEL, temperature=0.3, api_key=OPENAI_API_KEY,
).with_structured_output(SearchQueries)

_llm_self = ChatOpenAI(
    model=OPENAI_MODEL, temperature=0.5, api_key=OPENAI_API_KEY,
)

_llm_extract = ChatOpenAI(
    model=OPENAI_MODEL, temperature=0.2, api_key=OPENAI_API_KEY,
).with_structured_output(ResearchData)

MAX_SEARCHES = 3


# ── Branch 1: Tavily web search ───────────────────────────────────────────────

async def _web_research(topic: str) -> str:
    queries_result: SearchQueries = await _llm_queries.ainvoke([
        SystemMessage(content=RESEARCHER_QUERIES_SYSTEM),
        HumanMessage(content=f"Khái niệm/chủ đề cần nghiên cứu: {topic}"),
    ])
    queries = queries_result.queries[:MAX_SEARCHES]
    log.info("[Researcher/Web] queries: %s", queries)

    results_lists = await asyncio.gather(*[search(q) for q in queries])
    snippets: list[str] = []
    for query, results in zip(queries, results_lists):
        snippets.append(f"[Query: {query}]")
        for r in results:
            if r["body"]:
                snippets.append(f"• {r['title']}: {r['body'][:400]}")
    text = "\n".join(snippets)
    log.info("[Researcher/Web] %d chars collected", len(text))
    return text


# ── Branch 2: Wikipedia ───────────────────────────────────────────────────────

async def _wiki_research(topic: str) -> str:
    text = await fetch_summary(topic)
    log.info("[Researcher/Wiki] %d chars", len(text))
    return text


# ── Branch 3: LLM self-knowledge ─────────────────────────────────────────────

async def _self_research(topic: str) -> str:
    response = await _llm_self.ainvoke([
        SystemMessage(content=SELF_RESEARCH_SYSTEM),
        HumanMessage(content=f"Topic: {topic}"),
    ])
    text = response.content.strip()
    log.info("[Researcher/Self] %d chars", len(text))
    return text


# ── Merge & extract ───────────────────────────────────────────────────────────

async def _extract_research(topic: str, web: str, wiki: str, self_knowledge: str) -> ResearchData:
    combined = (
        f"=== WEB SEARCH ===\n{web or '(no results)'}\n\n"
        f"=== WIKIPEDIA ===\n{wiki or '(not found)'}\n\n"
        f"=== LLM SELF-KNOWLEDGE ===\n{self_knowledge or '(empty)'}"
    )
    prompt = (
        f"Chủ đề: {topic}\n\n"
        f"Dữ liệu từ 3 nguồn:\n{combined[:6000]}\n\n"
        "Tổng hợp thành dữ liệu giảng dạy đầy đủ, trả về JSON đúng schema."
    )
    return await _llm_extract.ainvoke([
        SystemMessage(content=RESEARCHER_EXTRACT_SYSTEM),
        HumanMessage(content=prompt),
    ])


# ── Main node ─────────────────────────────────────────────────────────────────

async def researcher_node(state: GraphState) -> dict:
    topic = state["topic"]
    log.info("[Researcher] START topic=%r", topic)

    cached = await get_cached_research(topic)
    if cached:
        log.info("[Researcher] cache hit for %r", topic)
        return {"research": cached, "status": "researched"}

    # 3 branches in parallel
    web_text, wiki_text, self_text = await asyncio.gather(
        _web_research(topic),
        _wiki_research(topic),
        _self_research(topic),
    )

    research: ResearchData = await _extract_research(topic, web_text, wiki_text, self_text)
    data = research.model_dump()

    await save_research_cache(topic, data)
    log.info(
        "[Researcher] DONE — %d facts, %d mechanisms, %d examples",
        len(data["key_facts"]), len(data["mechanisms"]), len(data["examples"]),
    )
    return {"research": data, "status": "researched"}
