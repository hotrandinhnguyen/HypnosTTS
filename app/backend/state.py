from typing import TypedDict, Optional


class GraphState(TypedDict):
    topic: str
    outline: Optional[dict]          # serialized Outline
    enriched_outline: Optional[dict] # serialized EnrichedOutline
    status: str
