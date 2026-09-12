# @covers analysis:EXT-011
# @covers analysis:DLT-033
import json

import pytest

from konspekt.features.notes.domain.notes import BlockKind, NoteBlock, NoteSection, Notes
from konspekt.features.quiz.adapters.outbound.claude_cli_quiz import ClaudeCliQuizGeneration
from konspekt.features.quiz.application.artifact import QuizArtifactError
from konspekt.features.quiz.domain.quiz import QuestionType, QuizConfig
from konspekt.shared.claude_cli import ClaudeCliError, ClaudeCliResult
from konspekt.shared.timecode import TimeRange
from tests.features.claude_fakes import FakeCliRunner, RecordingBudget


def a_notes() -> Notes:
    return Notes(
        title="Введение в термодинамику",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Первое начало",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text="Энергия сохраняется."),),
            ),
        ),
    )


def a_quiz_response_text() -> str:
    return json.dumps(
        {
            "questions": [
                {
                    "question_id": "q1",
                    "type": "multi_select",
                    "prompt": "Какие утверждения верны?",
                    "options": ["Энергия", "Энтропия", "Температура", "Давление"],
                    "correct_options": [0, 1],
                    "model_answer": None,
                    "rubric": None,
                    "section_id": "s1",
                },
                {
                    "question_id": "q2",
                    "type": "open",
                    "prompt": "Сформулируйте первое начало.",
                    "options": None,
                    "correct_options": None,
                    "model_answer": "Энергия изолированной системы сохраняется.",
                    "rubric": {
                        "max_points": 4,
                        "concepts": [
                            {"description": "Названа энергия", "points": 2},
                            {"description": "Указана изолированная система", "points": 2},
                        ],
                    },
                    "section_id": "s1",
                },
            ]
        }
    )


def test_generate_returns_quiz_and_charges_reported_cost() -> None:
    budget = RecordingBudget()
    runner = FakeCliRunner(ClaudeCliResult(text=a_quiz_response_text(), cost_usd=0.07))
    generation = ClaudeCliQuizGeneration(budget=budget, runner=runner)

    quiz = generation.generate(a_notes(), QuizConfig())

    assert quiz.questions[0].type is QuestionType.MULTI_SELECT
    assert quiz.questions[1].type is QuestionType.OPEN
    assert quiz.questions[1].rubric is not None
    assert quiz.questions[1].rubric.max_points == 4
    assert budget.charged_usd == [pytest.approx(0.07)]


def test_generate_forwards_model_and_grants_no_tools() -> None:
    runner = FakeCliRunner(ClaudeCliResult(text=a_quiz_response_text(), cost_usd=0.07))
    generation = ClaudeCliQuizGeneration(budget=RecordingBudget(), runner=runner)

    generation.generate(a_notes(), QuizConfig())

    assert runner.calls[0]["model"] == "claude-opus-5"
    assert runner.calls[0]["allowed_tools"] == ()


def test_prompt_embeds_schema_with_three_types_and_rubric() -> None:
    runner = FakeCliRunner(ClaudeCliResult(text=a_quiz_response_text(), cost_usd=0.07))
    generation = ClaudeCliQuizGeneration(budget=RecordingBudget(), runner=runner)

    generation.generate(a_notes(), QuizConfig())

    prompt = runner.calls[0]["prompt"]
    assert "single_choice" in prompt
    assert "multi_select" in prompt
    assert "rubric" in prompt
    assert "max_points" in prompt


def test_generate_retries_once_after_schema_mismatch_and_returns_second_result() -> None:
    budget = RecordingBudget()
    runner = FakeCliRunner(
        ClaudeCliResult(text="{}", cost_usd=0.05),
        ClaudeCliResult(text=a_quiz_response_text(), cost_usd=0.06),
    )
    generation = ClaudeCliQuizGeneration(budget=budget, runner=runner)

    quiz = generation.generate(a_notes(), QuizConfig())

    assert len(quiz.questions) == 2
    assert len(runner.calls) == 2
    assert budget.charged_usd == [pytest.approx(0.05), pytest.approx(0.06)]


def test_generate_fails_after_second_schema_mismatch() -> None:
    budget = RecordingBudget()
    runner = FakeCliRunner(
        ClaudeCliResult(text="{}", cost_usd=0.05),
        ClaudeCliResult(text="{}", cost_usd=0.05),
    )
    generation = ClaudeCliQuizGeneration(budget=budget, runner=runner)

    with pytest.raises(QuizArtifactError):
        generation.generate(a_notes(), QuizConfig())

    assert len(runner.calls) == 2
    assert len(budget.charged_usd) == 2


def test_coverage_feedback_is_injected_into_prompt() -> None:
    runner = FakeCliRunner(ClaudeCliResult(text=a_quiz_response_text(), cost_usd=0.07))
    generation = ClaudeCliQuizGeneration(budget=RecordingBudget(), runner=runner)

    generation.generate(
        a_notes(), QuizConfig(), coverage_feedback="sections s6 have fewer than 1 question(s)"
    )

    prompt = runner.calls[0]["prompt"]
    assert "PREVIOUS ATTEMPT REJECTED" in prompt
    assert "s6" in prompt


def test_generate_propagates_cli_error_without_retry() -> None:
    budget = RecordingBudget()
    runner = FakeCliRunner(ClaudeCliError("claude model run failed: boom"))
    generation = ClaudeCliQuizGeneration(budget=budget, runner=runner)

    with pytest.raises(ClaudeCliError, match="boom"):
        generation.generate(a_notes(), QuizConfig())

    assert len(runner.calls) == 1
    assert budget.charged_usd == []
