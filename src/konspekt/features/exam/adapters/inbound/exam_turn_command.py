import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from konspekt.features.exam.adapters.inbound.exam_input_error import ExamInputError
from konspekt.features.exam.adapters.inbound.open_turn_request import OpenTurnRequest
from konspekt.features.exam.adapters.inbound.quiz_document import parse_quiz
from konspekt.features.exam.adapters.inbound.reply_turn_request import ReplyTurnRequest
from konspekt.features.exam.adapters.inbound.turn_document import parse_turn
from konspekt.features.exam.adapters.inbound.turn_output import turn_output
from konspekt.features.exam.adapters.outbound.claude_cli_examiner import (
    ClaudeCliExaminer,
)
from konspekt.features.exam.application.examiner_inconsistency_error import (
    ExaminerInconsistencyError,
)
from konspekt.features.exam.application.open_turn import open_turn
from konspekt.features.exam.application.reply_turn import ReplyTurn
from konspekt.features.exam.application.turn_outcome import TurnOutcome
from konspekt.features.exam.domain.exam_quiz import ExamQuiz
from konspekt.features.exam.ports.outbound.examiner_model import ExaminerModelPort
from konspekt.features.exam.ports.outbound.examiner_model_error import (
    ExaminerModelError,
)

_NOTES_FILE_NAME = "konspekt.md"
_QUIZ_FILE_NAME = "quiz.json"
_TURN_FILE_NAME = "turn.json"
_EXAMINER_FAILED_EXIT_CODE = 1
_INVALID_INPUT_EXIT_CODE = 2


def main() -> None:
    sys.exit(run_exam_turn(sys.argv[1:], ClaudeCliExaminer))


def run_exam_turn(
    arguments: Sequence[str], examiner_for_notes: Callable[[str], ExaminerModelPort]
) -> int:
    if len(arguments) != 1:
        print("usage: konspekt-exam-turn <dir>", file=sys.stderr)
        return _INVALID_INPUT_EXIT_CODE
    exam_dir = Path(arguments[0])
    try:
        lecture_notes = _text_file(exam_dir / _NOTES_FILE_NAME)
        quiz = parse_quiz(_json_file(exam_dir / _QUIZ_FILE_NAME))
        request = parse_turn(_json_file(exam_dir / _TURN_FILE_NAME), quiz)
    except ExamInputError as error:
        print(f"error: {error}", file=sys.stderr)
        return _INVALID_INPUT_EXIT_CODE
    try:
        outcome = _outcome(quiz, request, lambda: examiner_for_notes(lecture_notes))
    except (ExaminerModelError, ExaminerInconsistencyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return _EXAMINER_FAILED_EXIT_CODE
    print(json.dumps(turn_output(outcome, quiz)))
    return 0


def _outcome(
    quiz: ExamQuiz,
    request: OpenTurnRequest | ReplyTurnRequest,
    examiner: Callable[[], ExaminerModelPort],
) -> TurnOutcome:
    if isinstance(request, OpenTurnRequest):
        return open_turn(quiz)
    return ReplyTurn(examiner()).run(
        quiz, request.state, request.messages, request.student_message
    )


def _json_file(path: Path) -> object:
    try:
        return json.loads(_text_file(path))
    except json.JSONDecodeError as error:
        raise ExamInputError(f"{path.name} is not valid JSON: {error}") from error


def _text_file(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ExamInputError(f"{path.name} is missing") from error
    except (OSError, UnicodeDecodeError) as error:
        raise ExamInputError(f"{path.name} is unreadable: {error}") from error
    if not text.strip():
        raise ExamInputError(f"{path.name} is empty")
    return text
