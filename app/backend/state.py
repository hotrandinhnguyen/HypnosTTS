from typing import TypedDict, Optional


class GraphState(TypedDict):
    topic: str
    instruct: str
    research: Optional[dict]      # serialized ResearchData
    analogy: Optional[dict]       # serialized Analogy
    script: Optional[str]         # full written TTS script
    review: Optional[dict]        # serialized ReviewResult
    revision_count: int
    status: str
