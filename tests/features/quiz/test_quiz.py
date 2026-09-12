# @covers analysis:DLT-033
# @covers analysis:CON-023
from collections.abc import Callable

import pytest

from konspekt.features.quiz.domain.quiz import (
    QuestionType,
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


def a_single_choice(**overrides: object) -> QuizQuestion:
    fields: dict[str, object] = {
        "question_id": "q1",
        "type": QuestionType.SINGLE_CHOICE,
        "prompt": "Что сохраняется?",
        "section_id": "s1",
        "options": ("Энергия", "Энтропия", "Температура", "Давление"),
        "correct_options": (0,),
    }
    fields.update(overrides)
    return QuizQuestion(**fields)


def a_multi_select(**overrides: object) -> QuizQuestion:
    fields: dict[str, object] = {
        "question_id": "q2",
        "type": QuestionType.MULTI_SELECT,
        "prompt": "Какие величины сохраняются?",
        "section_id": "s1",
        "options": ("Энергия", "Импульс", "Температура", "Давление"),
        "correct_options": (0, 1),
    }
    fields.update(overrides)
    return QuizQuestion(**fields)


def an_open(**overrides: object) -> QuizQuestion:
    fields: dict[str, object] = {
        "question_id": "q3",
        "type": QuestionType.OPEN,
        "prompt": "Сформулируйте первое начало.",
        "section_id": "s1",
        "model_answer": "Энергия изолированной системы сохраняется.",
        "rubric": a_rubric(),
    }
    fields.update(overrides)
    return QuizQuestion(**fields)


def test_question_type_values_match_contract() -> None:
    assert [member.value for member in QuestionType] == [
        "single_choice",
        "multi_select",
        "open",
    ]


def test_valid_single_choice_is_constructed() -> None:
    question = a_single_choice()

    assert question.correct_options == (0,)
    assert question.rubric is None


def test_valid_multi_select_is_constructed() -> None:
    question = a_multi_select()

    assert question.correct_options == (0, 1)


def test_valid_open_carries_rubric() -> None:
    question = an_open()

    assert question.rubric == a_rubric()


def test_single_choice_with_two_correct_options_is_rejected() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        a_single_choice(correct_options=(0, 2))


def test_multi_select_with_one_correct_option_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least two"):
        a_multi_select(correct_options=(0,))


def test_multi_select_with_duplicate_correct_options_is_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        a_multi_select(correct_options=(1, 1))


@pytest.mark.parametrize("builder", [a_single_choice, a_multi_select])
def test_choice_question_with_three_options_is_rejected(
    builder: Callable[..., QuizQuestion],
) -> None:
    with pytest.raises(ValueError, match="options"):
        builder(options=("а", "б", "в"))


@pytest.mark.parametrize("builder", [a_single_choice, a_multi_select])
def test_choice_question_with_model_answer_is_rejected(
    builder: Callable[..., QuizQuestion],
) -> None:
    with pytest.raises(ValueError, match="model_answer"):
        builder(model_answer="Энергия.")


@pytest.mark.parametrize("builder", [a_single_choice, a_multi_select])
def test_choice_question_with_rubric_is_rejected(
    builder: Callable[..., QuizQuestion],
) -> None:
    with pytest.raises(ValueError, match="rubric"):
        builder(rubric=a_rubric())


def test_choice_question_with_out_of_range_index_is_rejected() -> None:
    with pytest.raises(ValueError, match="0..3"):
        a_single_choice(correct_options=(4,))


def test_open_without_model_answer_is_rejected() -> None:
    with pytest.raises(ValueError, match="model_answer"):
        an_open(model_answer=None)


def test_open_without_rubric_is_rejected() -> None:
    with pytest.raises(ValueError, match="rubric"):
        an_open(rubric=None)


def test_open_with_options_is_rejected() -> None:
    with pytest.raises(ValueError, match="options"):
        an_open(options=("а", "б", "в", "г"))


def test_open_with_correct_options_is_rejected() -> None:
    with pytest.raises(ValueError, match="correct_options"):
        an_open(correct_options=(0,))


def test_rubric_with_points_not_summing_to_max_points_is_rejected() -> None:
    with pytest.raises(ValueError, match="sum"):
        Rubric(
            max_points=5,
            concepts=(
                RubricConcept(description="Первый пункт", points=2),
                RubricConcept(description="Второй пункт", points=1),
            ),
        )


def test_rubric_without_concepts_is_rejected() -> None:
    with pytest.raises(ValueError, match="concept"):
        Rubric(max_points=3, concepts=())


def test_rubric_concept_with_zero_points_is_rejected() -> None:
    with pytest.raises(ValueError, match="points"):
        RubricConcept(description="Пункт", points=0)
