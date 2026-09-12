from dataclasses import dataclass

from konspekt.features.exam.domain.asked_question import AskedQuestion
from konspekt.features.exam.domain.exam_message import ExamMessage
from konspekt.features.exam.domain.verdict import Verdict


@dataclass(frozen=True, slots=True)
class ExaminerTurn:
    lecture_language: str
    current: AskedQuestion
    follow_up_if_correct: AskedQuestion | None
    follow_up_if_wrong: AskedQuestion | None
    messages: tuple[ExamMessage, ...]
    student_message: str
    required_verdict: Verdict | None = None
