# @covers service:EXT-003
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from konspekt.features.exam.adapters.outbound.claude_cli_examiner import (
    ClaudeCliExaminer,
)
from konspekt.features.exam.adapters.outbound.examiner_protocol import (
    EXAMINER_PROTOCOL,
    TURN_SCHEMA,
)
from konspekt.features.exam.domain.answer_grading import AnswerGrading
from konspekt.features.exam.domain.answer_intent import AnswerIntent
from konspekt.features.exam.domain.asked_question import AskedQuestion
from konspekt.features.exam.domain.exam_message import ExamMessage
from konspekt.features.exam.domain.message_role import MessageRole
from konspekt.features.exam.domain.question_form import QuestionForm
from konspekt.features.exam.domain.question_type import QuestionType
from konspekt.features.exam.domain.verdict import Verdict
from konspekt.features.exam.domain.video_time_range import VideoTimeRange
from konspekt.features.exam.ports.outbound.examiner_assessment import ExaminerAssessment
from konspekt.features.exam.ports.outbound.examiner_model_error import (
    ExaminerModelError,
)
from konspekt.features.exam.ports.outbound.examiner_turn import ExaminerTurn
from konspekt.shared.claude_cli import ClaudeCliError, ClaudeCliResult
from tests.features.exam.exam_builders import (
    LECTURE_NOTES,
    a_choice_question,
    an_open_question,
)


@dataclass(frozen=True)
class RecordedCall:
    prompt: str
    model: str
    tools: tuple[str, ...] | None
    system_prompt: str
    json_schema: Mapping[str, object] | None


class FakeRunner:
    def __init__(self, *outcomes: ClaudeCliResult | ClaudeCliError) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[RecordedCall] = []

    def run(
        self,
        prompt: str,
        model: str,
        allowed_tools: tuple[str, ...] = (),
        tools: tuple[str, ...] | None = None,
        system_prompt_file: Path | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> ClaudeCliResult:
        system_prompt = (
            system_prompt_file.read_text(encoding="utf-8") if system_prompt_file else ""
        )
        self.calls.append(
            RecordedCall(prompt, model, tools, system_prompt, json_schema)
        )
        outcome = self._outcomes[len(self.calls) - 1]
        if isinstance(outcome, ClaudeCliError):
            raise outcome
        return outcome


def a_structured_result(cost_usd: float = 0.04, **overrides: object) -> ClaudeCliResult:
    structured_output = {
        "intent": "answer",
        "selected_options": ["A"],
        "covered_concepts": None,
        "stated_verdict": "correct",
        "reply": "Correct. Next question.",
        **overrides,
    }
    return ClaudeCliResult(
        text=json.dumps(structured_output),
        cost_usd=cost_usd,
        structured_output=structured_output,
    )


def a_turn(
    current: AskedQuestion | None = None,
    follow_up: AskedQuestion | None = None,
    required_verdict: Verdict | None = None,
) -> ExaminerTurn:
    next_question = follow_up or AskedQuestion(
        an_open_question("q2"), QuestionForm.ORIGINAL
    )
    return ExaminerTurn(
        lecture_language="en",
        current=current
        or AskedQuestion(a_choice_question("q1"), QuestionForm.ORIGINAL),
        follow_up_if_correct=next_question,
        follow_up_if_wrong=next_question,
        messages=(ExamMessage(MessageRole.EXAMINER, "Question 1 of 2: ..."),),
        student_message="I think it is A",
        required_verdict=required_verdict,
    )


def turn_input(runner: FakeRunner, call_index: int = 0) -> dict[str, object]:
    return json.loads(runner.calls[call_index].prompt)


def an_examiner(runner: FakeRunner) -> ClaudeCliExaminer:
    return ClaudeCliExaminer(lecture_notes=LECTURE_NOTES, runner=runner)


def test_examiner_runs_sonnet_with_every_tool_disabled() -> None:
    runner = FakeRunner(a_structured_result())

    an_examiner(runner).assess(a_turn())

    assert (runner.calls[0].model, runner.calls[0].tools) == ("sonnet", ())


def test_examiner_system_prompt_file_holds_the_protocol_and_the_whole_notes() -> None:
    runner = FakeRunner(a_structured_result())

    an_examiner(runner).assess(a_turn())

    assert (
        runner.calls[0].system_prompt
        == f"{EXAMINER_PROTOCOL}\n# Lecture notes\n\n{LECTURE_NOTES}"
    )


def test_examiner_passes_the_turn_schema() -> None:
    runner = FakeRunner(a_structured_result())

    an_examiner(runner).assess(a_turn())

    assert runner.calls[0].json_schema == TURN_SCHEMA


def test_examiner_reads_the_structured_output_and_the_run_cost() -> None:
    runner = FakeRunner(
        a_structured_result(
            cost_usd=0.07,
            selected_options=["B", "D"],
            stated_verdict="incorrect",
            reply="No.",
        )
    )

    assessment = an_examiner(runner).assess(a_turn())

    assert assessment == ExaminerAssessment(
        intent=AnswerIntent.ANSWER,
        grading=AnswerGrading(
            selected_options=frozenset({1, 3}), covered_concepts=frozenset()
        ),
        stated_verdict=Verdict.INCORRECT,
        reply="No.",
        llm_spend_usd=0.07,
    )


def test_examiner_maps_covered_concept_numbers_to_rubric_concepts() -> None:
    runner = FakeRunner(
        a_structured_result(selected_options=None, covered_concepts=[1, 3])
    )
    open_turn = a_turn(
        current=AskedQuestion(an_open_question("q2"), QuestionForm.ORIGINAL)
    )

    assessment = an_examiner(runner).assess(open_turn)

    assert assessment.grading == AnswerGrading(
        selected_options=frozenset(), covered_concepts=frozenset({0, 2})
    )


def test_schema_mismatch_is_rerequested_once() -> None:
    missing_output = ClaudeCliResult(
        text="free text", cost_usd=0.01, structured_output=None
    )
    runner = FakeRunner(missing_output, a_structured_result(cost_usd=0.04))

    assessment = an_examiner(runner).assess(a_turn())

    assert (len(runner.calls), assessment.llm_spend_usd) == (2, pytest.approx(0.05))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"intent": "guess"}, "intent has an unknown value"),
        (
            {"selected_options": ["E"]},
            "selected_options must be letters among A, B, C, D",
        ),
        ({"stated_verdict": "partly"}, "stated_verdict has an unknown value"),
        ({"reply": "  "}, "reply must be a non-empty string"),
    ],
    ids=["unknown intent", "unknown option letter", "unknown verdict", "blank reply"],
)
def test_second_schema_mismatch_raises_a_typed_error(
    overrides: dict[str, object], message: str
) -> None:
    mismatch = a_structured_result(**overrides)
    runner = FakeRunner(mismatch, mismatch)

    with pytest.raises(ExaminerModelError, match=message):
        an_examiner(runner).assess(a_turn())


@pytest.mark.parametrize("concept_number", [0, 4], ids=["below range", "above range"])
def test_concept_number_outside_the_rubric_is_a_schema_mismatch(
    concept_number: int,
) -> None:
    mismatch = a_structured_result(
        selected_options=None, covered_concepts=[concept_number]
    )
    runner = FakeRunner(mismatch, mismatch)
    open_turn = a_turn(
        current=AskedQuestion(an_open_question("q2"), QuestionForm.ORIGINAL)
    )

    with pytest.raises(ExaminerModelError, match="covered_concepts"):
        an_examiner(runner).assess(open_turn)


@pytest.mark.parametrize(
    "cli_error",
    [
        ClaudeCliError("claude model run failed: overloaded"),
        ClaudeCliError("claude exited with 1: boom"),
    ],
    ids=["is_error", "non-zero exit"],
)
def test_cli_failure_raises_a_typed_error_without_a_rerequest(
    cli_error: ClaudeCliError,
) -> None:
    runner = FakeRunner(cli_error)

    with pytest.raises(ExaminerModelError, match="claude"):
        an_examiner(runner).assess(a_turn())
    assert len(runner.calls) == 1


def test_turn_prompt_carries_the_choice_answer_key_as_letters() -> None:
    """# @covers service:REQ-004"""
    runner = FakeRunner(a_structured_result())
    question = a_choice_question("q1", QuestionType.MULTI_SELECT, frozenset({0, 2}))

    an_examiner(runner).assess(
        a_turn(current=AskedQuestion(question, QuestionForm.ORIGINAL))
    )

    assert turn_input(runner)["current_question"]["answer_key"] == {
        "correct_options": ["A", "C"]
    }


def test_turn_prompt_carries_the_open_rubric_with_its_passing_points() -> None:
    """# @covers service:REQ-004"""
    runner = FakeRunner(
        a_structured_result(selected_options=None, covered_concepts=[1])
    )

    an_examiner(runner).assess(
        a_turn(current=AskedQuestion(an_open_question("q2"), QuestionForm.ORIGINAL))
    )

    answer_key = turn_input(runner)["current_question"]["answer_key"]
    assert (
        answer_key["max_points"],
        answer_key["passing_points"],
        len(answer_key["concepts"]),
    ) == (5, 4, 3)


def test_turn_prompt_carries_the_section_title_of_the_current_question() -> None:
    """# @covers service:REQ-004"""
    runner = FakeRunner(a_structured_result())

    an_examiner(runner).assess(a_turn())

    assert (
        turn_input(runner)["current_question"]["section_title"]
        == "Course Introduction and Goals"
    )


@pytest.mark.parametrize(
    ("start_seconds", "end_seconds", "label"),
    [(0.0, 179.0, "00:00-02:59"), (3599.0, 3725.5, "59:59-1:02:05")],
    ids=["minutes", "hours"],
)
def test_turn_prompt_carries_the_video_time_range(
    start_seconds: float, end_seconds: float, label: str
) -> None:
    """# @covers service:REQ-004"""
    runner = FakeRunner(a_structured_result())
    question = replace(
        a_choice_question("q1"), time_range=VideoTimeRange(start_seconds, end_seconds)
    )

    an_examiner(runner).assess(
        a_turn(current=AskedQuestion(question, QuestionForm.ORIGINAL))
    )

    assert turn_input(runner)["current_question"]["video_time_range"] == label


def test_turn_prompt_carries_both_follow_up_questions_without_their_keys() -> None:
    """# @covers service:REQ-004"""
    runner = FakeRunner(a_structured_result())

    an_examiner(runner).assess(a_turn())

    prompt_input = turn_input(runner)
    follow_ups = [
        prompt_input["follow_up_if_correct"],
        prompt_input["follow_up_if_wrong"],
    ]
    assert [(view["question_id"], "answer_key" in view) for view in follow_ups] == [
        ("q2", False),
        ("q2", False),
    ]


def test_reworded_choice_follow_up_is_marked_to_be_asked_as_open_without_options() -> (
    None
):
    """# @covers service:REQ-004"""
    runner = FakeRunner(a_structured_result())
    reworded = AskedQuestion(a_choice_question("q1"), QuestionForm.REWORDED)

    an_examiner(runner).assess(a_turn(follow_up=reworded))

    follow_up = turn_input(runner)["follow_up_if_wrong"]
    assert (follow_up["form"], follow_up["asked_as"], follow_up["options"]) == (
        "reworded",
        "open",
        None,
    )


def test_rerequest_prompt_carries_the_required_verdict() -> None:
    """# @covers service:REQ-004"""
    runner = FakeRunner(a_structured_result())

    an_examiner(runner).assess(a_turn(required_verdict=Verdict.INCORRECT))

    assert turn_input(runner)["required_verdict"] == "incorrect"
