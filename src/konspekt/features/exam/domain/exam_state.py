from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Self

from konspekt.features.exam.domain.question_form import QuestionForm
from konspekt.features.exam.domain.question_progress import QuestionProgress
from konspekt.features.exam.domain.question_status import QuestionStatus
from konspekt.features.exam.domain.queued_question import QueuedQuestion
from konspekt.features.exam.domain.verdict import Verdict


@dataclass(frozen=True, slots=True)
class ExamState:
    queue: tuple[QueuedQuestion, ...]
    questions: tuple[QuestionProgress, ...]

    @classmethod
    def initial(cls, question_ids: Sequence[str]) -> Self:
        return cls(
            queue=tuple(
                QueuedQuestion(question_id, QuestionForm.ORIGINAL)
                for question_id in question_ids
            ),
            questions=tuple(
                QuestionProgress(question_id, QuestionStatus.PENDING, attempts=0)
                for question_id in question_ids
            ),
        )

    def current(self) -> QueuedQuestion | None:
        return self.queue[0] if self.queue else None

    def mastered_count(self) -> int:
        return sum(
            1
            for progress in self.questions
            if progress.status is QuestionStatus.MASTERED
        )

    def is_mastered(self) -> bool:
        return self.mastered_count() == len(self.questions)

    def after(self, verdict: Verdict) -> Self:
        current, *rest = self.queue
        if verdict is Verdict.CORRECT:
            return type(self)(
                queue=tuple(rest),
                questions=self._progress_with(
                    current.question_id, QuestionProgress.as_mastered
                ),
            )
        return type(self)(
            queue=(*rest, QueuedQuestion(current.question_id, QuestionForm.REWORDED)),
            questions=self._progress_with(
                current.question_id, QuestionProgress.as_failed
            ),
        )

    def _progress_with(
        self, question_id: str, change: Callable[[QuestionProgress], QuestionProgress]
    ) -> tuple[QuestionProgress, ...]:
        return tuple(
            change(progress) if progress.question_id == question_id else progress
            for progress in self.questions
        )
