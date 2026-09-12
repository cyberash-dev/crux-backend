from typing import Protocol

from konspekt.features.notes.domain.notes import Notes
from konspekt.features.quiz.domain.quiz import Quiz, QuizConfig


class QuizGenerationPort(Protocol):
    def generate(
        self, notes: Notes, config: QuizConfig, coverage_feedback: str | None = None
    ) -> Quiz: ...
