from konspekt.features.exam.adapters.inbound.state_document import state_payload
from konspekt.features.exam.application.turn_outcome import TurnOutcome
from konspekt.features.exam.domain.exam_quiz import ExamQuiz
from konspekt.features.exam.domain.exam_state import ExamState
from konspekt.features.exam.domain.graded_answer import GradedAnswer


def turn_output(outcome: TurnOutcome, quiz: ExamQuiz) -> dict[str, object]:
    return {
        "state": state_payload(outcome.state),
        "progress": _progress(outcome.state, quiz),
        "examiner_message": outcome.examiner_message,
        "graded": _graded(outcome.graded),
        "is_mastered": outcome.state.is_mastered(),
        "llm_spend_usd": outcome.llm_spend_usd,
    }


def _progress(state: ExamState, quiz: ExamQuiz) -> dict[str, object]:
    current = state.current()
    return {
        "total": len(state.questions),
        "mastered": state.mastered_count(),
        "current_question_id": None if current is None else current.question_id,
        "questions": [
            {
                "question_id": progress.question_id,
                "section_title": quiz.question(progress.question_id).section_title,
                "status": progress.status.value,
                "attempts": progress.attempts,
            }
            for progress in state.questions
        ],
    }


def _graded(graded: GradedAnswer | None) -> dict[str, str] | None:
    if graded is None:
        return None
    return {"question_id": graded.question_id, "verdict": graded.verdict.value}
