from langgraph.graph import StateGraph, START, END

from app.backend.state import GraphState
from app.backend.agents.researcher import researcher_node
from app.backend.agents.analogy import analogy_node
from app.backend.agents.writer import writer_node
from app.backend.agents.reviewer import reviewer_node

MAX_REVISIONS = 2


def _route_after_review(state: GraphState) -> str:
    review = state.get("review") or {}
    revision_count = state.get("revision_count", 0)
    if review.get("passed") or revision_count >= MAX_REVISIONS:
        return END
    return "writer"


def build_graph():
    g = StateGraph(GraphState)

    g.add_node("researcher", researcher_node)
    g.add_node("analogy", analogy_node)
    g.add_node("writer", writer_node)
    g.add_node("reviewer", reviewer_node)

    g.add_edge(START, "researcher")
    g.add_edge("researcher", "analogy")
    g.add_edge("analogy", "writer")
    g.add_edge("writer", "reviewer")
    g.add_conditional_edges("reviewer", _route_after_review, {END: END, "writer": "writer"})

    return g.compile()
