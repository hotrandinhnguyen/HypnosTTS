from pydantic import BaseModel


class Concept(BaseModel):
    name: str
    definition: str       # what it is, in plain language
    why_it_matters: str   # why the listener should care
    how_it_works: str     # mechanism / intuition (not formula)
    example: str          # concrete, real-world example
    misconception: str    # the #1 wrong belief people hold


class Distinction(BaseModel):
    pair: list[str]       # exactly 2 items
    explanation: str      # what separates them in practice


class Outline(BaseModel):
    topic: str
    intro: str            # hook paragraph — why this topic is fascinating
    concepts: list[Concept]   # 6-10 core concepts
    distinctions: list[Distinction]   # 2-4 pairs commonly confused
    summary: str          # what the listener should walk away knowing


class EnrichedConcept(BaseModel):
    name: str
    definition: str
    why_it_matters: str
    how_it_works: str
    example: str
    misconception: str
    analogy: str          # memorable analogy that makes it click
    deeper_note: str      # non-obvious insight or surprising fact


class EnrichedOutline(BaseModel):
    topic: str
    intro: str
    concepts: list[EnrichedConcept]
    distinctions: list[Distinction]
    summary: str
