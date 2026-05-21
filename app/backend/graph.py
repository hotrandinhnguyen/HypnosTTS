from langgraph.graph import StateGraph, START, END

from app.backend.state import GraphState
from app.backend.agents.planner import planner_node
from app.backend.agents.researcher import researcher_node


def build_graph():
    """Graph chỉ gồm Planner → Researcher.
    Writer chạy riêng ngoài graph để stream real-time sang TTS."""
    g = StateGraph(GraphState)

    g.add_node("planner", planner_node)
    g.add_node("researcher", researcher_node)

    g.add_edge(START, "planner")
    g.add_edge("planner", "researcher")
    g.add_edge("researcher", END)

    return g.compile()
