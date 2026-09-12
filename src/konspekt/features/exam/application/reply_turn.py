import logging
from collections.abc import Sequence
from dataclasses import replace

from konspekt.features.exam.application.examiner_inconsistency_error import (
    ExaminerInconsistencyError,
)
from konspekt.features.exam.application.turn_outcome import TurnOutcome
from konspekt.features.exam.domain.answer_intent import AnswerIntent
from konspekt.features.exam.domain.asked_question import AskedQuestion
from konspekt.features.exam.domain.exam_message import ExamMessage
from konspekt.features.exam.domain.exam_quiz import ExamQuiz
from konspekt.features.exam.domain.exam_state import ExamState
from konspekt.features.exam.domain.graded_answer import GradedAnswer
from konspekt.features.exam.domain.queued_question import QueuedQuestion
from konspekt.features.exam.domain.verdict import Verdict
from konspekt.features.exam.ports.outbound.examiner_assessment import ExaminerAssessment
from konspekt.features.exam.ports.outbound.examiner_model import ExaminerModelPort
from konspekt.features.exam.ports.outbound.examiner_turn import ExaminerTurn

_logger = logging.getLogger(__name__)


class ReplyTurn:
    def __init__(self, examiner: ExaminerModelPort) -> None:
        self._examiner = examiner

    def run(
        self,
        quiz: ExamQuiz,
        state: ExamState,
        messages: Sequence[ExamMessage],
        student_message: str,
    ) -> TurnOutcome:
        current = state.current()
        if current is None:
            raise ValueError("a reply turn needs a question left to ask")
        turn = ExaminerTurn(
            lecture_language=quiz.language,
            current=quiz.asked(current),
            follow_up_if_correct=_asked(quiz, state.after(Verdict.CORRECT).current()),
            follow_up_if_wrong=_asked(quiz, state.after(Verdict.INCORRECT).current()),
            messages=tuple(messages),
            student_message=student_message,
        )
        assessment = self._examiner.assess(turn)
        if assessment.intent is not AnswerIntent.ANSWER:
            return TurnOutcome(state, assessment.reply, None, assessment.llm_spend_usd)
        verdict = turn.current.verdict(assessment.grading)
        if assessment.stated_verdict is not verdict:
            assessment = self._restated(turn, verdict, assessment)
        return TurnOutcome(
            state=state.after(verdict),
            examiner_message=assessment.reply,
            graded=GradedAnswer(current.question_id, verdict),
            llm_spend_usd=assessment.llm_spend_usd,
        )

    def _restated(
        self, turn: ExaminerTurn, verdict: Verdict, first: ExaminerAssessment
    ) -> ExaminerAssessment:
        _logger.warning(
            "exam.verdict_rerequested",
            extra={
                "question_id": turn.current.question.question_id,
                "stated_verdict": first.stated_verdict,
                "computed_verdict": verdict.value,
            },
        )
        restated = self._examiner.assess(replace(turn, required_verdict=verdict))
        if (
            restated.intent is not AnswerIntent.ANSWER
            or restated.stated_verdict is not verdict
        ):
            raise ExaminerInconsistencyError(
                f"examiner stated {restated.stated_verdict} for question "
                f"{turn.current.question.question_id} after the re-request, computed {verdict.value}"
            )
        return replace(
            restated, llm_spend_usd=first.llm_spend_usd + restated.llm_spend_usd
        )


def _asked(quiz: ExamQuiz, queued: QueuedQuestion | None) -> AskedQuestion | None:
    return quiz.asked(queued) if queued is not None else None
