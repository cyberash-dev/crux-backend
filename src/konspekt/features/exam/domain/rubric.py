from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

from konspekt.features.exam.domain.rubric_concept import RubricConcept


@dataclass(frozen=True, slots=True)
class Rubric:
    max_points: int
    concepts: tuple[RubricConcept, ...]
    passing_points: int

    @classmethod
    def with_mastery_threshold(
        cls, max_points: int, concepts: tuple[RubricConcept, ...]
    ) -> Self:
        # ceil(0.8 * max_points) in integers: the float product 0.8 * 15 ceils to 13, not 12
        return cls(
            max_points=max_points,
            concepts=concepts,
            passing_points=-(-4 * max_points // 5),
        )

    @classmethod
    def requiring_every_concept(cls, concept_descriptions: Sequence[str]) -> Self:
        concepts = tuple(
            RubricConcept(description=text, points=1) for text in concept_descriptions
        )
        return cls(
            max_points=len(concepts), concepts=concepts, passing_points=len(concepts)
        )

    def is_passed_by(self, covered_concepts: frozenset[int]) -> bool:
        covered_points = sum(self.concepts[index].points for index in covered_concepts)
        return covered_points >= self.passing_points
