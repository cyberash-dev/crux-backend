from konspekt.features.exam.application.opening_message import opening_message
from konspekt.features.exam.application.turn_outcome import TurnOutcome
from konspekt.features.exam.domain.exam_quiz import ExamQuiz
from konspekt.features.exam.domain.exam_state import ExamState


def open_turn(quiz: ExamQuiz) -> TurnOutcome:
    return TurnOutcome(
        state=ExamState.initial(quiz.question_ids()),
        examiner_message=opening_message(quiz),
        graded=None,
        llm_spend_usd=0.0,
    )
