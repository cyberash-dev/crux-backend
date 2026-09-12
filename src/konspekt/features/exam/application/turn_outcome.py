from dataclasses import dataclass

from konspekt.features.exam.domain.exam_state import ExamState
from konspekt.features.exam.domain.graded_answer import GradedAnswer


@dataclass(frozen=True, slots=True)
class TurnOutcome:
    state: ExamState
    examiner_message: str
    graded: GradedAnswer | None
    llm_spend_usd: float
