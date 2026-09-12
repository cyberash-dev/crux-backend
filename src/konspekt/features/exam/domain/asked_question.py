from dataclasses import dataclass

from konspekt.features.exam.domain.answer_grading import AnswerGrading
from konspekt.features.exam.domain.exam_question import ExamQuestion
from konspekt.features.exam.domain.question_form import QuestionForm
from konspekt.features.exam.domain.question_type import QuestionType
from konspekt.features.exam.domain.rubric import Rubric
from konspekt.features.exam.domain.verdict import Verdict


@dataclass(frozen=True, slots=True)
class AskedQuestion:
    question: ExamQuestion
    form: QuestionForm

    def asked_type(self) -> QuestionType:
        if self.form is QuestionForm.REWORDED:
            return QuestionType.OPEN
        return self.question.type

    def rubric(self) -> Rubric | None:
        if self.asked_type() is not QuestionType.OPEN:
            return None
        if self.question.rubric is not None:
            return self.question.rubric
        return Rubric.requiring_every_concept(self.question.correct_option_texts())

    def verdict(self, grading: AnswerGrading) -> Verdict:
        rubric = self.rubric()
        if rubric is None:
            is_correct = grading.selected_options == self.question.correct_options
        else:
            is_correct = rubric.is_passed_by(grading.covered_concepts)
        return Verdict.CORRECT if is_correct else Verdict.INCORRECT
