# @covers analysis:EXT-010
# @covers analysis:DLT-033
import json

import pytest

from konspekt.features.notes.domain.notes import BlockKind, NoteBlock, NoteSection, Notes
from konspekt.features.quiz.adapters.outbound.claude_quiz import (
    QUIZ_MAX_TOKENS,
    QUIZ_RESPONSE_SCHEMA,
    ClaudeQuizGeneration,
    QuizGenerationRefusedError,
    build_quiz_prompt,
    parse_quiz_response,
)
from konspekt.features.quiz.application.artifact import QuizArtifactError
from konspekt.features.quiz.domain.quiz import QuestionType, QuizConfig
from konspekt.shared.timecode import TimeRange
from tests.features.claude_fakes import FakeClient, RecordingBudget, a_message


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
                subsections=(
                    NoteSection(
                        section_id="s1.1",
                        title="Работа и теплота",
                        source_spans=(TimeRange(30.0, 60.0),),
                        blocks=(NoteBlock(kind=BlockKind.PROSE, text="Работа и теплота."),),
                    ),
                ),
            ),
            NoteSection(
                section_id="s2",
                title="Второе начало",
                source_spans=(TimeRange(60.0, 120.0),),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text="Энтропия не убывает."),),
            ),
        ),
    )


def a_quiz_response_payload() -> dict[str, object]:
    return {
        "questions": [
            {
                "question_id": "q1",
                "type": "single_choice",
                "prompt": "Что сохраняется по первому началу?",
                "options": ["Энергия", "Энтропия", "Температура", "Давление"],
                "correct_options": [0],
                "model_answer": None,
                "rubric": None,
                "section_id": "s1",
            },
            {
                "question_id": "q2",
                "type": "multi_select",
                "prompt": "Какие утверждения верны?",
                "options": ["Энергия сохраняется", "Энтропия не убывает", "Т растёт", "P падает"],
                "correct_options": [0, 1],
                "model_answer": None,
                "rubric": None,
                "section_id": "s1",
            },
            {
                "question_id": "q3",
                "type": "open",
                "prompt": "Сформулируйте второе начало.",
                "options": None,
                "correct_options": None,
                "model_answer": "Энтропия изолированной системы не убывает.",
                "rubric": {
                    "max_points": 3,
                    "concepts": [
                        {"description": "Названа энтропия", "points": 2},
                        {"description": "Указана изолированная система", "points": 1},
                    ],
                },
                "section_id": "s2",
            },
        ]
    }


def test_prompt_carries_language_counts_and_sections() -> None:
    prompt = build_quiz_prompt(a_notes(), QuizConfig())

    assert "ru" in prompt
    assert "10" in prompt
    assert "7" in prompt
    assert "3" in prompt
    assert "s1" in prompt
    assert "Первое начало" in prompt
    assert "Энергия сохраняется." in prompt


def test_prompt_states_rules_for_all_three_question_types() -> None:
    prompt = build_quiz_prompt(a_notes(), QuizConfig())

    assert "single_choice" in prompt
    assert "multi_select" in prompt
    assert "'open'" in prompt
    assert "exactly ONE" in prompt
    assert "TWO OR MORE" in prompt
    assert "correct_options" in prompt


def test_prompt_states_rubric_rules() -> None:
    prompt = build_quiz_prompt(a_notes(), QuizConfig())

    assert "rubric" in prompt
    assert "max_points" in prompt
    assert "between 3 and 6" in prompt
    assert "2-4" in prompt
    assert "sum" in prompt
    assert "language of the notes" in prompt


def test_prompt_requires_full_section_coverage() -> None:
    config = QuizConfig()

    prompt = build_quiz_prompt(a_notes(), config)

    assert "s1" in prompt
    assert "s2" in prompt
    assert str(config.target_for(2)) in prompt
    assert str(config.questions_per_section) in prompt


def test_prompt_covers_transition_and_summary_sections() -> None:
    prompt = build_quiz_prompt(a_notes(), QuizConfig())

    assert "transition" in prompt
    assert "summary" in prompt


def test_response_schema_carries_three_types_and_rubric() -> None:
    question_schema = QUIZ_RESPONSE_SCHEMA["properties"]["questions"]["items"]

    assert question_schema["properties"]["type"]["enum"] == [
        "single_choice",
        "multi_select",
        "open",
    ]
    assert "rubric" in question_schema["properties"]
    assert "rubric" in question_schema["required"]


def test_coverage_feedback_is_injected_into_prompt() -> None:
    client = FakeClient(a_message(json.dumps(a_quiz_response_payload())))
    generation = ClaudeQuizGeneration(budget=RecordingBudget(), client=client)

    generation.generate(
        a_notes(), QuizConfig(), coverage_feedback="sections s6 have fewer than 1 question(s)"
    )

    prompt = client.stream_requests[0]["messages"][0]["content"]
    assert "PREVIOUS ATTEMPT REJECTED" in prompt
    assert "s6" in prompt


def test_without_feedback_prompt_carries_no_rejection_paragraph() -> None:
    client = FakeClient(a_message(json.dumps(a_quiz_response_payload())))
    generation = ClaudeQuizGeneration(budget=RecordingBudget(), client=client)

    generation.generate(a_notes(), QuizConfig())

    prompt = client.stream_requests[0]["messages"][0]["content"]
    assert "PREVIOUS ATTEMPT REJECTED" not in prompt


def test_prompt_lists_subsections_and_demands_top_level_coverage() -> None:
    prompt = build_quiz_prompt(a_notes(), QuizConfig())

    assert "s1.1" in prompt
    assert "subsection of s1" in prompt
    assert "Работа и теплота." in prompt
    assert "TOP-LEVEL" in prompt
    assert "may target subsections" in prompt


def test_parse_quiz_response_builds_domain_quiz() -> None:
    quiz = parse_quiz_response(json.dumps(a_quiz_response_payload()))

    assert len(quiz.questions) == 3
    assert quiz.questions[0].type is QuestionType.SINGLE_CHOICE
    assert quiz.questions[1].type is QuestionType.MULTI_SELECT
    assert quiz.questions[2].type is QuestionType.OPEN
    assert quiz.questions[2].model_answer == "Энтропия изолированной системы не убывает."
    assert quiz.questions[2].rubric is not None
    assert quiz.questions[2].rubric.max_points == 3


def test_parse_quiz_response_rejects_malformed_json() -> None:
    with pytest.raises(QuizArtifactError, match="JSON"):
        parse_quiz_response("{not json")


def test_generate_charges_budget_from_reported_usage() -> None:
    budget = RecordingBudget()
    client = FakeClient(a_message(json.dumps(a_quiz_response_payload())))
    generation = ClaudeQuizGeneration(budget=budget, client=client)

    generation.generate(a_notes(), QuizConfig())

    assert budget.charged_usd == [
        pytest.approx(1000 * 5 / 1_000_000 + 2000 * 25 / 1_000_000)
    ]


def test_generate_sends_structured_output_request_without_sampling_overrides() -> None:
    client = FakeClient(a_message(json.dumps(a_quiz_response_payload())))
    generation = ClaudeQuizGeneration(budget=RecordingBudget(), client=client)

    generation.generate(a_notes(), QuizConfig())

    request = client.stream_requests[0]
    assert request["model"] == "claude-opus-5"
    assert request["max_tokens"] == QUIZ_MAX_TOKENS
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert "thinking" not in request
    assert "temperature" not in request


def test_generate_retries_once_after_schema_mismatch_and_returns_second_result() -> None:
    budget = RecordingBudget()
    client = FakeClient(
        a_message("{}"),
        a_message(json.dumps(a_quiz_response_payload())),
    )
    generation = ClaudeQuizGeneration(budget=budget, client=client)

    quiz = generation.generate(a_notes(), QuizConfig())

    assert len(quiz.questions) == 3
    assert len(client.stream_requests) == 2
    assert len(budget.charged_usd) == 2


def test_generate_fails_after_second_schema_mismatch() -> None:
    budget = RecordingBudget()
    client = FakeClient(a_message("{}"), a_message("{}"))
    generation = ClaudeQuizGeneration(budget=budget, client=client)

    with pytest.raises(QuizArtifactError):
        generation.generate(a_notes(), QuizConfig())

    assert len(client.stream_requests) == 2
    assert len(budget.charged_usd) == 2


def test_generate_raises_typed_error_on_refusal() -> None:
    budget = RecordingBudget()
    client = FakeClient(
        a_message(json.dumps(a_quiz_response_payload()), stop_reason="refusal")
    )
    generation = ClaudeQuizGeneration(budget=budget, client=client)

    with pytest.raises(QuizGenerationRefusedError):
        generation.generate(a_notes(), QuizConfig())

    assert len(budget.charged_usd) == 1
