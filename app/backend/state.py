from typing import TypedDict, Optional


class GraphState(TypedDict):
    topic: str
    instruct: str
    target_minutes: int           # 0 = default (18-23 min)
    research: Optional[dict]      # serialized ResearchData
    analogy: Optional[dict]       # serialized Analogy
    script: Optional[str]         # full written TTS script
    review: Optional[dict]        # serialized ReviewResult
    revision_count: int
    status: str
