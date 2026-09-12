from konspekt.features.exam.adapters.inbound.exam_input_error import ExamInputError
from konspekt.features.exam.adapters.inbound.json_fields import (
    json_enum,
    json_list,
    json_object,
    json_text,
)
from konspekt.features.exam.adapters.inbound.open_turn_request import OpenTurnRequest
from konspekt.features.exam.adapters.inbound.reply_turn_request import ReplyTurnRequest
from konspekt.features.exam.adapters.inbound.state_document import parse_state
from konspekt.features.exam.domain.exam_message import ExamMessage
from konspekt.features.exam.domain.exam_quiz import ExamQuiz
from konspekt.features.exam.domain.message_role import MessageRole


def parse_turn(raw_turn: object, quiz: ExamQuiz) -> OpenTurnRequest | ReplyTurnRequest:
    fields = json_object(raw_turn, "turn")
    turn_kind = fields.get("kind")
    if turn_kind == "open":
        return OpenTurnRequest()
    if turn_kind != "reply":
        raise ExamInputError("turn kind must be open or reply")
    state = parse_state(fields.get("state"), quiz)
    if state.current() is None:
        raise ExamInputError("state has no question left to ask")
    return ReplyTurnRequest(
        state=state,
        messages=tuple(
            _message(raw) for raw in json_list(fields.get("messages"), "turn messages")
        ),
        student_message=json_text(
            fields.get("student_message"), "turn student_message"
        ),
    )


def _message(raw_message: object) -> ExamMessage:
    fields = json_object(raw_message, "turn message")
    return ExamMessage(
        role=json_enum(MessageRole, fields.get("role"), "turn message role"),
        text=json_text(fields.get("text"), "turn message text"),
    )
