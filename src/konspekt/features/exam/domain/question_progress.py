from dataclasses import dataclass, replace
from typing import Self

from konspekt.features.exam.domain.question_status import QuestionStatus


@dataclass(frozen=True, slots=True)
class QuestionProgress:
    question_id: str
    status: QuestionStatus
    attempts: int

    def as_mastered(self) -> Self:
        return replace(self, status=QuestionStatus.MASTERED)

    def as_failed(self) -> Self:
        return replace(self, status=QuestionStatus.FAILED, attempts=self.attempts + 1)
