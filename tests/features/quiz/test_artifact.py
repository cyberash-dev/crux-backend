# @covers analysis:CON-023
# @covers analysis:DLT-021
# @covers analysis:DLT-033
import pytest

from konspekt.features.quiz.application.artifact import (
    QuizArtifactError,
    parse_quiz_payload,
    quiz_payload,
)
from konspekt.features.quiz.domain.quiz import (
    QuestionType,
    Quiz,
    QuizQuestion,
    Rubric,
    RubricConcept,
)


def a_rubric() -> Rubric:
    return Rubric(
        max_points=3,
        concepts=(
            RubricConcept(description="Названо сохранение энергии", points=2),
            RubricConcept(description="Указана изолированная система", points=1),
        ),
    )


def a_quiz() -> Quiz:
    return Quiz(
        questions=(
            QuizQuestion(
                question_id="q1",
                type=QuestionType.SINGLE_CHOICE,
                prompt="Что сохраняется по первому началу?",
                section_id="s1",
                options=("Энергия", "Энтропия", "Температура", "Давление"),
                correct_options=(0,),
            ),
            QuizQuestion(
                question_id="q2",
                type=QuestionType.MULTI_SELECT,
                prompt="Какие величины сохраняются?",
                section_id="s1",
                options=("Энергия", "Импульс", "Температура", "Давление"),
                correct_options=(0, 1),
            ),
            QuizQuestion(
                question_id="q3",
                type=QuestionType.OPEN,
                prompt="Сформулируйте первое начало термодинамики.",
                section_id="s1",
                model_answer="Энергия изолированной системы сохраняется.",
                rubric=a_rubric(),
            ),
        )
    )


def a_question_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "question_id": "q1",
        "type": "single_choice",
        "prompt": "Что сохраняется по первому началу?",
        "options": ["Энергия", "Энтропия", "Температура", "Давление"],
        "correct_options": [0],
        "model_answer": None,
        "rubric": None,
        "section_id": "s1",
    }
    payload.update(overrides)
    return payload


def test_round_trip_preserves_quiz() -> None:
    quiz = a_quiz()

    restored = parse_quiz_payload(quiz_payload(quiz))

    assert restored == quiz


def test_payload_uses_contract_field_names() -> None:
    payload = quiz_payload(a_quiz())

    assert set(payload) == {"questions"}
    assert set(payload["questions"][0]) == {
        "question_id",
        "type",
        "prompt",
        "options",
        "correct_options",
        "model_answer",
        "rubric",
        "section_id",
    }


def test_open_question_rubric_is_serialized_as_contract_object() -> None:
    payload = quiz_payload(a_quiz())

    assert payload["questions"][2]["rubric"] == {
        "max_points": 3,
        "concepts": [
            {"description": "Названо сохранение энергии", "points": 2},
            {"description": "Указана изолированная система", "points": 1},
        ],
    }


def test_choice_question_rubric_is_serialized_as_null() -> None:
    payload = quiz_payload(a_quiz())

    assert payload["questions"][0]["rubric"] is None
    assert payload["questions"][1]["rubric"] is None


def test_single_choice_with_two_correct_options_is_rejected() -> None:
    payload = {"questions": [a_question_payload(correct_options=[0, 2])]}

    with pytest.raises(QuizArtifactError, match="exactly one"):
        parse_quiz_payload(payload)


def test_multi_select_with_one_correct_option_is_rejected() -> None:
    payload = {
        "questions": [a_question_payload(type="multi_select", correct_options=[0])]
    }

    with pytest.raises(QuizArtifactError, match="at least two"):
        parse_quiz_payload(payload)


def test_choice_question_with_three_options_is_rejected() -> None:
    payload = {
        "questions": [a_question_payload(options=["Энергия", "Энтропия", "Температура"])]
    }

    with pytest.raises(QuizArtifactError, match="options"):
        parse_quiz_payload(payload)


def test_open_question_with_correct_options_is_rejected() -> None:
    payload = {
        "questions": [
            a_question_payload(
                type="open",
                options=None,
                correct_options=[1],
                model_answer="Энергия сохраняется.",
                rubric={"max_points": 1, "concepts": [{"description": "х", "points": 1}]},
            )
        ]
    }

    with pytest.raises(QuizArtifactError, match="correct_options"):
        parse_quiz_payload(payload)


def test_open_question_with_bad_rubric_sum_is_rejected() -> None:
    payload = {
        "questions": [
            a_question_payload(
                type="open",
                options=None,
                correct_options=None,
                model_answer="Энергия сохраняется.",
                rubric={
                    "max_points": 5,
                    "concepts": [{"description": "Пункт", "points": 2}],
                },
            )
        ]
    }

    with pytest.raises(QuizArtifactError, match="sum"):
        parse_quiz_payload(payload)


def test_choice_question_with_rubric_is_rejected() -> None:
    payload = {
        "questions": [
            a_question_payload(
                rubric={"max_points": 1, "concepts": [{"description": "х", "points": 1}]}
            )
        ]
    }

    with pytest.raises(QuizArtifactError, match="rubric"):
        parse_quiz_payload(payload)


def test_legacy_mcq_with_one_correct_option_parses_as_single_choice() -> None:
    payload = {"questions": [a_question_payload(type="mcq", correct_options=[2])]}

    quiz = parse_quiz_payload(payload)

    assert quiz.questions[0].type is QuestionType.SINGLE_CHOICE
    assert quiz.questions[0].correct_options == (2,)


def test_legacy_mcq_with_two_correct_options_parses_as_multi_select() -> None:
    payload = {"questions": [a_question_payload(type="mcq", correct_options=[0, 2])]}

    quiz = parse_quiz_payload(payload)

    assert quiz.questions[0].type is QuestionType.MULTI_SELECT
    assert quiz.questions[0].correct_options == (0, 2)


def an_open_question_payload_without_rubric_field() -> dict[str, object]:
    question = a_question_payload(
        type="open",
        options=None,
        correct_options=None,
        model_answer="Энергия изолированной системы сохраняется.",
    )
    del question["rubric"]
    return question


@pytest.mark.parametrize(
    "question",
    [
        pytest.param(
            a_question_payload(
                type="open",
                options=None,
                correct_options=None,
                model_answer="Энергия сохраняется.",
                rubric=None,
            ),
            id="null-rubric",
        ),
        pytest.param(an_open_question_payload_without_rubric_field(), id="absent-rubric-field"),
    ],
)
def test_open_question_without_rubric_is_rejected(question: dict[str, object]) -> None:
    """# @covers analysis:CON-023"""
    payload = {"questions": [question]}

    with pytest.raises(QuizArtifactError, match="open question requires rubric"):
        parse_quiz_payload(payload)


def test_legacy_correct_option_field_is_rejected_with_rename_hint() -> None:
    question = a_question_payload()
    del question["correct_options"]
    question["correct_option"] = 0

    with pytest.raises(QuizArtifactError, match="correct_options"):
        parse_quiz_payload({"questions": [question]})


def test_choice_question_with_empty_correct_options_is_rejected() -> None:
    payload = {"questions": [a_question_payload(correct_options=[])]}

    with pytest.raises(QuizArtifactError, match="correct_options"):
        parse_quiz_payload(payload)


def test_unknown_question_type_is_rejected() -> None:
    payload = {"questions": [a_question_payload(type="truefalse")]}

    with pytest.raises(QuizArtifactError, match="truefalse"):
        parse_quiz_payload(payload)


def test_missing_required_field_is_rejected() -> None:
    question = a_question_payload()
    del question["prompt"]

    with pytest.raises(QuizArtifactError, match="prompt"):
        parse_quiz_payload({"questions": [question]})
