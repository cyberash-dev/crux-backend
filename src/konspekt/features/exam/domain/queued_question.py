from dataclasses import dataclass

from konspekt.features.exam.domain.question_form import QuestionForm


@dataclass(frozen=True, slots=True)
class QueuedQuestion:
    question_id: str
    form: QuestionForm
