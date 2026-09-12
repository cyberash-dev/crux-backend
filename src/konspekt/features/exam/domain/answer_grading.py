from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnswerGrading:
    selected_options: frozenset[int]
    covered_concepts: frozenset[int]
