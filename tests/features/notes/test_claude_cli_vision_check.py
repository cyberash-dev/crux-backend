# @covers analysis:EXT-011
# @covers analysis:INV-022
# @covers analysis:DLT-029
# @covers analysis:DLT-030
import json

import pytest

from konspekt.features.notes.adapters.outbound.claude_cli_vision_check import (
    ClaudeCliVisionCheck,
)
from konspekt.features.notes.domain.illustration import CandidateFit
from konspekt.shared.claude_cli import ClaudeCliError, ClaudeCliResult
from tests.features.claude_fakes import FakeCliRunner, RecordingBudget

IMAGE_PATH = "/work/images/radius_ulna.jpg"
PURPOSE = "Лучевая и локтевая кости, вид спереди"


def a_verdict_text(score: int = 80) -> str:
    return json.dumps({"score": score, "reason": "clear drawing"})


@pytest.mark.parametrize(
    "score, expected_fit",
    [(95, CandidateFit.PERFECT), (73, CandidateFit.SUITABLE), (20, CandidateFit.UNSUITABLE)],
)
def test_score_is_parsed_fit_derived_and_budget_charged(
    score: int, expected_fit: CandidateFit
) -> None:
    budget = RecordingBudget()
    runner = FakeCliRunner(ClaudeCliResult(text=a_verdict_text(score), cost_usd=0.03))

    assessment = ClaudeCliVisionCheck(budget=budget, runner=runner).assess(IMAGE_PATH, PURPOSE)

    assert assessment.fit is expected_fit
    assert assessment.score == score
    assert budget.charged_usd == [pytest.approx(0.03)]


def test_prompt_references_image_and_purpose_and_grants_read_tool() -> None:
    runner = FakeCliRunner(ClaudeCliResult(text=a_verdict_text(95), cost_usd=0.03))

    ClaudeCliVisionCheck(budget=RecordingBudget(), runner=runner).assess(IMAGE_PATH, PURPOSE)

    call = runner.calls[0]
    assert IMAGE_PATH in call["prompt"]
    assert PURPOSE in call["prompt"]
    assert '"score"' in call["prompt"]
    assert call["model"] == "claude-opus-5"
    assert call["allowed_tools"] == ("Read",)


def test_custom_model_is_forwarded() -> None:
    runner = FakeCliRunner(ClaudeCliResult(text=a_verdict_text(95), cost_usd=0.03))

    ClaudeCliVisionCheck(budget=RecordingBudget(), model="claude-sonnet-5", runner=runner).assess(
        IMAGE_PATH, PURPOSE
    )

    assert runner.calls[0]["model"] == "claude-sonnet-5"


def test_fenced_verdict_is_still_parsed() -> None:
    fenced = "```json\n" + a_verdict_text(55) + "\n```"
    runner = FakeCliRunner(ClaudeCliResult(text=fenced, cost_usd=0.03))

    assessment = ClaudeCliVisionCheck(budget=RecordingBudget(), runner=runner).assess(
        IMAGE_PATH, PURPOSE
    )

    assert assessment.fit is CandidateFit.SUITABLE
    assert assessment.score == 55


@pytest.mark.parametrize(
    "malformed_text",
    [
        "not json",
        json.dumps({"reason": "no score"}),
        json.dumps({"score": "high"}),
        json.dumps({"score": 150}),
        json.dumps({"score": True}),
        json.dumps([80]),
    ],
)
def test_malformed_answer_grades_unsuitable(malformed_text: str) -> None:
    runner = FakeCliRunner(ClaudeCliResult(text=malformed_text, cost_usd=0.03))

    assessment = ClaudeCliVisionCheck(budget=RecordingBudget(), runner=runner).assess(
        IMAGE_PATH, PURPOSE
    )

    assert assessment.fit is CandidateFit.UNSUITABLE
    assert assessment.score == 0


def test_runner_error_grades_unsuitable() -> None:
    runner = FakeCliRunner(ClaudeCliError("cli failed"))

    assessment = ClaudeCliVisionCheck(budget=RecordingBudget(), runner=runner).assess(
        IMAGE_PATH, PURPOSE
    )

    assert assessment.fit is CandidateFit.UNSUITABLE
