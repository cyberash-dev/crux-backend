from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RubricConcept:
    description: str
    points: int
