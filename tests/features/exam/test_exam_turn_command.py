# @covers service:CON-004
import json
from pathlib import Path

import pytest

from konspekt.features.exam.adapters.inbound.exam_turn_command import run_exam_turn
from konspekt.features.exam.domain.answer_intent import AnswerIntent
from konspekt.features.exam.domain.verdict import Verdict
from konspekt.features.exam.ports.outbound.examiner_model import ExaminerModelPort
from konspekt.features.exam.ports.outbound.examiner_model_error import (
    ExaminerModelError,
)
from tests.features.exam.exam_builders import (
    FakeExaminer,
    a_quiz_document,
    a_reply_document,
    a_state_document,
    an_assessment,
    an_exam_dir,
)

INITIAL_STATE = a_state_document(
    queue=[("q1", "original"), ("q2", "original")],
    questions=[("q1", "pending", 0), ("q2", "pending", 0)],
)
LAST_QUESTION_STATE = a_state_document(
    queue=[("q2", "original")],
    questions=[("q1", "mastered", 1), ("q2", "pending", 0)],
)


class ExaminerFactory:
    def __init__(self, examiner: FakeExaminer) -> None:
        self.examiner = examiner
        self.lecture_notes: list[str] = []

    def __call__(self, lecture_notes: str) -> ExaminerModelPort:
        self.lecture_notes.append(lecture_notes)
        return self.examiner


def turn_stdout(
    exam_dir: Path, factory: ExaminerFactory, capsys: pytest.CaptureFixture[str]
) -> dict[str, object]:
    exit_code = run_exam_turn([str(exam_dir)], factory)
    assert exit_code == 0
    return json.loads(capsys.readouterr().out)


def test_open_turn_asks_the_first_question_with_options_lettered_a_to_d(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exam_dir = an_exam_dir(tmp_path, {"kind": "open"})

    output = turn_stdout(exam_dir, ExaminerFactory(FakeExaminer()), capsys)

    assert str(output["examiner_message"]).endswith(
        "Question 1 of 2:\n"
        "Which activity binds solving, proving and arguing efficiency together?\n"
        "A. Communication of the solution\n"
        "B. Testing on many inputs\n"
        "C. Optimizing constant factors\n"
        "D. Choosing a language\n"
        "Choose one option."
    )


def test_open_turn_names_the_lecture(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exam_dir = an_exam_dir(tmp_path, {"kind": "open"})

    output = turn_stdout(exam_dir, ExaminerFactory(FakeExaminer()), capsys)

    assert str(output["examiner_message"]).startswith(
        'Exam on the lecture "Introduction to Algorithms".'
    )


@pytest.mark.parametrize(
    ("language", "heading"),
    [("ru", "Вопрос 1 из 2:"), ("en", "Question 1 of 2:"), ("de", "Question 1 of 2:")],
)
def test_open_turn_speaks_the_lecture_language_with_english_fallback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], language: str, heading: str
) -> None:
    exam_dir = an_exam_dir(
        tmp_path, {"kind": "open"}, quiz=a_quiz_document(language=language)
    )

    output = turn_stdout(exam_dir, ExaminerFactory(FakeExaminer()), capsys)

    assert heading in str(output["examiner_message"])


def test_open_turn_returns_every_question_pending(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exam_dir = an_exam_dir(tmp_path, {"kind": "open"})

    output = turn_stdout(exam_dir, ExaminerFactory(FakeExaminer()), capsys)

    assert output["progress"] == {
        "total": 2,
        "mastered": 0,
        "current_question_id": "q1",
        "questions": [
            {
                "question_id": "q1",
                "section_title": "Course Introduction and Goals",
                "status": "pending",
                "attempts": 0,
            },
            {
                "question_id": "q2",
                "section_title": "What Is a Computational Problem?",
                "status": "pending",
                "attempts": 0,
            },
        ],
    }


def test_open_turn_makes_no_model_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exam_dir = an_exam_dir(tmp_path, {"kind": "open"})
    factory = ExaminerFactory(FakeExaminer())

    output = turn_stdout(exam_dir, factory, capsys)

    assert (factory.lecture_notes, output["llm_spend_usd"], output["graded"]) == (
        [],
        0.0,
        None,
    )


def test_reply_turn_returns_the_graded_answer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exam_dir = an_exam_dir(
        tmp_path, a_reply_document(INITIAL_STATE, student_message="A")
    )
    examiner = FakeExaminer(
        an_assessment(selected_options=frozenset({0}), stated_verdict=Verdict.CORRECT)
    )

    output = turn_stdout(exam_dir, ExaminerFactory(examiner), capsys)

    assert (output["graded"], output["is_mastered"]) == (
        {"question_id": "q1", "verdict": "correct"},
        False,
    )


def test_reply_turn_returns_the_new_state_and_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exam_dir = an_exam_dir(
        tmp_path, a_reply_document(INITIAL_STATE, student_message="B")
    )
    examiner = FakeExaminer(
        an_assessment(selected_options=frozenset({1}), stated_verdict=Verdict.INCORRECT)
    )

    output = turn_stdout(exam_dir, ExaminerFactory(examiner), capsys)

    assert (
        output["state"],
        output["progress"]["current_question_id"],
        output["progress"]["mastered"],
    ) == (
        a_state_document(
            queue=[("q2", "original"), ("q1", "reworded")],
            questions=[("q1", "failed", 1), ("q2", "pending", 0)],
        ),
        "q2",
        0,
    )


def test_reply_turn_returns_the_examiner_reply_and_its_spend(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exam_dir = an_exam_dir(tmp_path, a_reply_document(INITIAL_STATE))
    examiner = FakeExaminer(
        an_assessment(
            selected_options=frozenset({0}),
            stated_verdict=Verdict.CORRECT,
            reply="Right. Next:",
            llm_spend_usd=0.03,
        )
    )

    output = turn_stdout(exam_dir, ExaminerFactory(examiner), capsys)

    assert (output["examiner_message"], output["llm_spend_usd"]) == (
        "Right. Next:",
        0.03,
    )


def test_reply_turn_keeps_earlier_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    earlier_state = a_state_document(
        queue=[("q2", "original"), ("q1", "reworded")],
        questions=[("q1", "failed", 1), ("q2", "pending", 0)],
    )
    exam_dir = an_exam_dir(
        tmp_path, a_reply_document(earlier_state, student_message="inputs of any size")
    )
    examiner = FakeExaminer(
        an_assessment(
            covered_concepts=frozenset({0, 2}), stated_verdict=Verdict.CORRECT
        )
    )

    output = turn_stdout(exam_dir, ExaminerFactory(examiner), capsys)

    assert output["state"] == a_state_document(
        queue=[("q1", "reworded")],
        questions=[("q1", "failed", 1), ("q2", "mastered", 0)],
    )


def test_non_answer_returns_graded_null_and_unchanged_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exam_dir = an_exam_dir(
        tmp_path,
        a_reply_document(INITIAL_STATE, student_message="What is a predicate?"),
    )
    examiner = FakeExaminer(an_assessment(intent=AnswerIntent.QUESTION))

    output = turn_stdout(exam_dir, ExaminerFactory(examiner), capsys)

    assert (output["graded"], output["state"]) == (None, INITIAL_STATE)


def test_last_mastered_question_sets_is_mastered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exam_dir = an_exam_dir(
        tmp_path,
        a_reply_document(LAST_QUESTION_STATE, student_message="inputs of any size"),
    )
    examiner = FakeExaminer(
        an_assessment(
            covered_concepts=frozenset({0, 1, 2}), stated_verdict=Verdict.CORRECT
        )
    )

    output = turn_stdout(exam_dir, ExaminerFactory(examiner), capsys)

    assert (
        output["is_mastered"],
        output["progress"]["current_question_id"],
        output["progress"]["mastered"],
    ) == (
        True,
        None,
        2,
    )


def test_reply_turn_gives_the_examiner_the_lecture_notes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exam_dir = an_exam_dir(tmp_path, a_reply_document(INITIAL_STATE))
    factory = ExaminerFactory(FakeExaminer(an_assessment(intent=AnswerIntent.OTHER)))

    turn_stdout(exam_dir, factory, capsys)

    assert factory.lecture_notes == [
        (exam_dir / "konspekt.md").read_text(encoding="utf-8")
    ]


@pytest.mark.parametrize("file_name", ["konspekt.md", "quiz.json", "turn.json"])
def test_missing_input_file_exits_2(tmp_path: Path, file_name: str) -> None:
    exam_dir = an_exam_dir(tmp_path, {"kind": "open"})
    (exam_dir / file_name).unlink()

    exit_code = run_exam_turn([str(exam_dir)], ExaminerFactory(FakeExaminer()))

    assert exit_code == 2


def test_missing_input_file_is_named_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exam_dir = an_exam_dir(tmp_path, {"kind": "open"})
    (exam_dir / "quiz.json").unlink()

    run_exam_turn([str(exam_dir)], ExaminerFactory(FakeExaminer()))

    assert capsys.readouterr() == ("", "error: quiz.json is missing\n")


@pytest.mark.parametrize(
    "turn",
    [
        {"kind": "resume"},
        a_reply_document({"queue": [], "questions": []}),
        a_reply_document(
            a_state_document(
                queue=[("q1", "original")],
                questions=[("q1", "pending", 0), ("q2", "pending", 0)],
            )
        ),
        a_reply_document(
            a_state_document(
                queue=[], questions=[("q1", "mastered", 0), ("q2", "mastered", 1)]
            )
        ),
        a_reply_document(INITIAL_STATE, student_message=""),
    ],
    ids=[
        "unknown kind",
        "state not matching the quiz",
        "unmastered question not queued",
        "mastered state",
        "empty message",
    ],
)
def test_malformed_turn_exits_2(tmp_path: Path, turn: dict[str, object]) -> None:
    exam_dir = an_exam_dir(tmp_path, turn)

    exit_code = run_exam_turn([str(exam_dir)], ExaminerFactory(FakeExaminer()))

    assert exit_code == 2


def test_quiz_that_is_not_json_exits_2(tmp_path: Path) -> None:
    exam_dir = an_exam_dir(tmp_path, {"kind": "open"})
    (exam_dir / "quiz.json").write_text("{not json", encoding="utf-8")

    exit_code = run_exam_turn([str(exam_dir)], ExaminerFactory(FakeExaminer()))

    assert exit_code == 2


def test_choice_question_without_four_options_exits_2(tmp_path: Path) -> None:
    quiz = a_quiz_document()
    quiz["questions"][0]["options"] = ["only", "three", "options"]
    exam_dir = an_exam_dir(tmp_path, {"kind": "open"}, quiz=quiz)

    exit_code = run_exam_turn([str(exam_dir)], ExaminerFactory(FakeExaminer()))

    assert exit_code == 2


def test_model_failure_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exam_dir = an_exam_dir(tmp_path, a_reply_document(INITIAL_STATE))
    examiner = FakeExaminer(ExaminerModelError("claude exited with 1: overloaded"))

    exit_code = run_exam_turn([str(exam_dir)], ExaminerFactory(examiner))

    assert (exit_code, capsys.readouterr()) == (
        1,
        ("", "error: claude exited with 1: overloaded\n"),
    )


def test_verdict_still_inconsistent_after_the_rerequest_exits_1(tmp_path: Path) -> None:
    exam_dir = an_exam_dir(
        tmp_path, a_reply_document(INITIAL_STATE, student_message="B")
    )
    claims_correct = an_assessment(
        selected_options=frozenset({1}), stated_verdict=Verdict.CORRECT
    )
    examiner = FakeExaminer(claims_correct, claims_correct)

    exit_code = run_exam_turn([str(exam_dir)], ExaminerFactory(examiner))

    assert exit_code == 1
