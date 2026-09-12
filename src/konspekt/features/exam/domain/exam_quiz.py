from dataclasses import dataclass

from konspekt.features.exam.domain.asked_question import AskedQuestion
from konspekt.features.exam.domain.exam_question import ExamQuestion
from konspekt.features.exam.domain.queued_question import QueuedQuestion


@dataclass(frozen=True, slots=True)
class ExamQuiz:
    lecture_title: str
    language: str
    questions: tuple[ExamQuestion, ...]

    def question_ids(self) -> tuple[str, ...]:
        return tuple(question.question_id for question in self.questions)

    def question(self, question_id: str) -> ExamQuestion:
        for question in self.questions:
            if question.question_id == question_id:
                return question
        raise KeyError(f"quiz has no question {question_id!r}")

    def asked(self, queued: QueuedQuestion) -> AskedQuestion:
        return AskedQuestion(self.question(queued.question_id), queued.form)
