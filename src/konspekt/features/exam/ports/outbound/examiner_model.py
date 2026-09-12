from typing import Protocol

from konspekt.features.exam.ports.outbound.examiner_assessment import ExaminerAssessment
from konspekt.features.exam.ports.outbound.examiner_turn import ExaminerTurn


class ExaminerModelPort(Protocol):
    def assess(self, turn: ExaminerTurn) -> ExaminerAssessment: ...
