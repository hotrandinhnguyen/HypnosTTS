from pydantic import BaseModel


class ResearchData(BaseModel):
    key_facts: list[str]
    mechanisms: list[str]
    examples: list[str]
    misconceptions: list[str]
    interesting_angles: list[str]
    comparisons: list[str]   # "[topic] vs [related]: key difference..."


class SearchQueries(BaseModel):
    queries: list[str]   # exactly 3 queries


class Analogy(BaseModel):
    image: str      # visual metaphor (e.g. "like a...")
    scenario: str   # story / scene that unfolds
    mapping: str    # direct structural mapping (A is to B as X is to Y)


class ReviewResult(BaseModel):
    passed: bool
    issues: list[str]
    suggestion: str
