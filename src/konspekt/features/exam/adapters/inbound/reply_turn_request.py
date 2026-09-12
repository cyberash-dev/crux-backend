from dataclasses import dataclass

from konspekt.features.exam.domain.exam_message import ExamMessage
from konspekt.features.exam.domain.exam_state import ExamState


@dataclass(frozen=True, slots=True)
class ReplyTurnRequest:
    state: ExamState
    messages: tuple[ExamMessage, ...]
    student_message: str
