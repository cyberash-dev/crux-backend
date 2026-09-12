# @covers service:INV-001
import pytest

from konspekt.features.exam.domain.answer_grading import AnswerGrading
from konspekt.features.exam.domain.asked_question import AskedQuestion
from konspekt.features.exam.domain.exam_state import ExamState
from konspekt.features.exam.domain.question_form import QuestionForm
from konspekt.features.exam.domain.question_progress import QuestionProgress
from konspekt.features.exam.domain.question_status import QuestionStatus
from konspekt.features.exam.domain.question_type import QuestionType
from konspekt.features.exam.domain.queued_question import QueuedQuestion
from konspekt.features.exam.domain.rubric import Rubric
from konspekt.features.exam.domain.rubric_concept import RubricConcept
from konspekt.features.exam.domain.verdict import Verdict
from tests.features.exam.exam_builders import (
    CHOICE_OPTIONS,
    a_choice_question,
    a_quiz,
    an_open_question,
)


def a_multi_select_question() -> AskedQuestion:
    question = a_choice_question(
        question_type=QuestionType.MULTI_SELECT, correct_options=frozenset({0, 1, 2})
    )
    return AskedQuestion(question, QuestionForm.ORIGINAL)


def selected(*options: int) -> AnswerGrading:
    return AnswerGrading(
        selected_options=frozenset(options), covered_concepts=frozenset()
    )


def covered(*concepts: int) -> AnswerGrading:
    return AnswerGrading(
        selected_options=frozenset(), covered_concepts=frozenset(concepts)
    )


def test_choice_answer_with_the_exact_option_set_is_correct() -> None:
    verdict = a_multi_select_question().verdict(selected(0, 1, 2))

    assert verdict is Verdict.CORRECT


@pytest.mark.parametrize(
    "answer",
    [selected(0, 1), selected(0, 1, 2, 3), selected()],
    ids=["subset", "superset", "nothing selected"],
)
def test_choice_answer_with_another_option_set_is_incorrect(
    answer: AnswerGrading,
) -> None:
    verdict = a_multi_select_question().verdict(answer)

    assert verdict is Verdict.INCORRECT


def test_open_answer_reaching_the_passing_points_is_correct() -> None:
    asked = AskedQuestion(
        an_open_question(concept_points=(2, 1, 2)), QuestionForm.ORIGINAL
    )

    verdict = asked.verdict(covered(0, 2))

    assert verdict is Verdict.CORRECT


def test_open_answer_one_point_below_the_passing_points_is_incorrect() -> None:
    asked = AskedQuestion(
        an_open_question(concept_points=(2, 1, 2)), QuestionForm.ORIGINAL
    )

    verdict = asked.verdict(covered(0, 1))

    assert verdict is Verdict.INCORRECT


@pytest.mark.parametrize(
    ("max_points", "passing_points"),
    [(1, 1), (3, 3), (5, 4), (10, 8), (15, 12)],
)
def test_passing_points_are_the_ceiling_of_eight_tenths_of_max_points(
    max_points: int, passing_points: int
) -> None:
    concepts = tuple(
        RubricConcept(description=f"c{index}", points=1) for index in range(max_points)
    )

    rubric = Rubric.with_mastery_threshold(max_points, concepts)

    assert rubric.passing_points == passing_points


def test_failed_choice_question_comes_back_as_an_open_question() -> None:
    quiz = a_quiz(a_choice_question("q1", QuestionType.MULTI_SELECT, frozenset({0, 2})))
    state = ExamState.initial(quiz.question_ids()).after(Verdict.INCORRECT)

    asked_again = quiz.asked(state.queue[0])

    assert asked_again.asked_type() is QuestionType.OPEN


def test_failed_choice_question_is_graded_by_one_one_point_concept_per_correct_option() -> (
    None
):
    quiz = a_quiz(a_choice_question("q1", QuestionType.MULTI_SELECT, frozenset({0, 2})))
    state = ExamState.initial(quiz.question_ids()).after(Verdict.INCORRECT)

    rubric = quiz.asked(state.queue[0]).rubric()

    assert rubric == Rubric(
        max_points=2,
        concepts=(
            RubricConcept(description=CHOICE_OPTIONS[0], points=1),
            RubricConcept(description=CHOICE_OPTIONS[2], points=1),
        ),
        passing_points=2,
    )


@pytest.mark.parametrize(
    ("answer", "expected_verdict"),
    [(covered(0, 1), Verdict.CORRECT), (covered(1), Verdict.INCORRECT)],
    ids=["every concept covered", "one concept missing"],
)
def test_reworded_choice_answer_is_correct_only_when_every_concept_is_covered(
    answer: AnswerGrading, expected_verdict: Verdict
) -> None:
    question = a_choice_question("q1", QuestionType.MULTI_SELECT, frozenset({0, 2}))
    asked = AskedQuestion(question, QuestionForm.REWORDED)

    verdict = asked.verdict(answer)

    assert verdict is expected_verdict


def test_failed_open_question_is_reasked_reworded_with_its_own_rubric() -> None:
    question = an_open_question("q2")
    quiz = a_quiz(question)
    state = ExamState.initial(quiz.question_ids()).after(Verdict.INCORRECT)

    asked_again = quiz.asked(state.queue[0])

    assert (asked_again.form, asked_again.rubric()) == (
        QuestionForm.REWORDED,
        question.rubric,
    )


def test_wrong_answer_moves_the_question_to_the_end_of_the_queue_reworded() -> None:
    state = ExamState.initial(["q1", "q2", "q3"])

    after_wrong = state.after(Verdict.INCORRECT)

    assert after_wrong.queue == (
        QueuedQuestion("q2", QuestionForm.ORIGINAL),
        QueuedQuestion("q3", QuestionForm.ORIGINAL),
        QueuedQuestion("q1", QuestionForm.REWORDED),
    )


def test_wrong_answer_marks_the_question_failed_and_counts_the_attempt() -> None:
    state = (
        ExamState.initial(["q1", "q2"]).after(Verdict.INCORRECT).after(Verdict.CORRECT)
    )

    after_second_wrong = state.after(Verdict.INCORRECT)

    assert after_second_wrong.questions[0] == QuestionProgress(
        "q1", QuestionStatus.FAILED, attempts=2
    )


def test_correct_answer_masters_the_question_and_removes_it_from_the_queue() -> None:
    state = ExamState.initial(["q1", "q2"])

    after_correct = state.after(Verdict.CORRECT)

    assert after_correct == ExamState(
        queue=(QueuedQuestion("q2", QuestionForm.ORIGINAL),),
        questions=(
            QuestionProgress("q1", QuestionStatus.MASTERED, attempts=0),
            QuestionProgress("q2", QuestionStatus.PENDING, attempts=0),
        ),
    )


def test_questions_are_asked_in_quiz_order() -> None:
    state = ExamState.initial(["q1", "q2", "q3"])

    assert [queued.question_id for queued in state.queue] == ["q1", "q2", "q3"]


def test_session_is_not_mastered_while_a_question_is_left() -> None:
    state = ExamState.initial(["q1", "q2"]).after(Verdict.CORRECT)

    assert state.is_mastered() is False


def test_session_is_mastered_after_the_last_question_is_mastered() -> None:
    state = (
        ExamState.initial(["q1", "q2"]).after(Verdict.INCORRECT).after(Verdict.CORRECT)
    )

    after_last = state.after(Verdict.CORRECT)

    assert after_last.is_mastered() is True
