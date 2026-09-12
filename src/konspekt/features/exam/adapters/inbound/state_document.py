from konspekt.features.exam.adapters.inbound.exam_input_error import ExamInputError
from konspekt.features.exam.adapters.inbound.json_fields import (
    json_count,
    json_enum,
    json_list,
    json_object,
    json_text,
)
from konspekt.features.exam.domain.exam_quiz import ExamQuiz
from konspekt.features.exam.domain.exam_state import ExamState
from konspekt.features.exam.domain.question_form import QuestionForm
from konspekt.features.exam.domain.question_progress import QuestionProgress
from konspekt.features.exam.domain.question_status import QuestionStatus
from konspekt.features.exam.domain.queued_question import QueuedQuestion


def parse_state(raw_state: object, quiz: ExamQuiz) -> ExamState:
    fields = json_object(raw_state, "state")
    questions = tuple(
        _progress(raw) for raw in json_list(fields.get("questions"), "state questions")
    )
    queue = tuple(_queued(raw) for raw in json_list(fields.get("queue"), "state queue"))
    if tuple(progress.question_id for progress in questions) != quiz.question_ids():
        raise ExamInputError(
            "state questions must list the quiz questions in quiz order"
        )
    queued_ids = [queued.question_id for queued in queue]
    unmastered_ids = {
        progress.question_id
        for progress in questions
        if progress.status is not QuestionStatus.MASTERED
    }
    if len(set(queued_ids)) != len(queued_ids) or set(queued_ids) != unmastered_ids:
        raise ExamInputError(
            "state queue must hold every unmastered question exactly once"
        )
    return ExamState(queue=queue, questions=questions)


def state_payload(state: ExamState) -> dict[str, object]:
    return {
        "queue": [
            {"question_id": queued.question_id, "form": queued.form.value}
            for queued in state.queue
        ],
        "questions": [
            {
                "question_id": progress.question_id,
                "status": progress.status.value,
                "attempts": progress.attempts,
            }
            for progress in state.questions
        ],
    }


def _progress(raw_progress: object) -> QuestionProgress:
    fields = json_object(raw_progress, "state question")
    return QuestionProgress(
        question_id=json_text(fields.get("question_id"), "state question_id"),
        status=json_enum(QuestionStatus, fields.get("status"), "state question status"),
        attempts=json_count(
            fields.get("attempts"), "state question attempts", minimum=0
        ),
    )


def _queued(raw_queued: object) -> QueuedQuestion:
    fields = json_object(raw_queued, "state queue entry")
    return QueuedQuestion(
        question_id=json_text(fields.get("question_id"), "state queue question_id"),
        form=json_enum(QuestionForm, fields.get("form"), "state queue form"),
    )
