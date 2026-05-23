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


class ChunkAnalysis(BaseModel):
    start: int       # sentence index where this chunk starts
    concept: str     # specific concept being explained right now
    metaphor: str    # exact analogy/example used ("" if none)
    visual_core: str # if drawing 1 image to explain this, what to draw
    mood: str        # emotional tone: dramatic/curious/calm/wonder/analytical

class ChunkAnalysisList(BaseModel):
    chunks: list[ChunkAnalysis]  # 40-55 chunks


class ChunkPrompt(BaseModel):
    start: int   # sentence index where this image starts
    prompt: str  # English image prompt for this semantic chunk

class ChunkPromptList(BaseModel):
    chunks: list[ChunkPrompt]  # 40-55 prompts
