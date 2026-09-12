from dataclasses import dataclass

from konspekt.features.exam.domain.answer_grading import AnswerGrading
from konspekt.features.exam.domain.answer_intent import AnswerIntent
from konspekt.features.exam.domain.verdict import Verdict


@dataclass(frozen=True, slots=True)
class ExaminerAssessment:
    intent: AnswerIntent
    grading: AnswerGrading
    stated_verdict: Verdict | None
    reply: str
    llm_spend_usd: float
