# @covers service:REQ-004
# @covers service:INV-001
import pytest

from konspekt.features.exam.application.examiner_inconsistency_error import (
    ExaminerInconsistencyError,
)
from konspekt.features.exam.application.reply_turn import ReplyTurn
from konspekt.features.exam.domain.answer_intent import AnswerIntent
from konspekt.features.exam.domain.asked_question import AskedQuestion
from konspekt.features.exam.domain.exam_message import ExamMessage
from konspekt.features.exam.domain.exam_state import ExamState
from konspekt.features.exam.domain.graded_answer import GradedAnswer
from konspekt.features.exam.domain.message_role import MessageRole
from konspekt.features.exam.domain.question_form import QuestionForm
from konspekt.features.exam.domain.verdict import Verdict
from tests.features.exam.exam_builders import (
    FakeExaminer,
    a_choice_question,
    a_quiz,
    an_assessment,
    an_open_question,
)

OPENING = (ExamMessage(MessageRole.EXAMINER, "Question 1 of 2: ..."),)


def test_turn_asks_the_examiner_about_the_current_question_with_both_follow_ups() -> (
    None
):
    quiz = a_quiz(a_choice_question("q1"), an_open_question("q2"))
    examiner = FakeExaminer(
        an_assessment(selected_options=frozenset({0}), stated_verdict=Verdict.CORRECT)
    )

    ReplyTurn(examiner).run(quiz, ExamState.initial(quiz.question_ids()), OPENING, "A")

    turn = examiner.turns[0]
    assert (turn.current, turn.follow_up_if_correct, turn.follow_up_if_wrong) == (
        AskedQuestion(quiz.questions[0], QuestionForm.ORIGINAL),
        AskedQuestion(quiz.questions[1], QuestionForm.ORIGINAL),
        AskedQuestion(quiz.questions[1], QuestionForm.ORIGINAL),
    )


def test_last_question_left_comes_back_reworded_if_wrong_and_closes_if_correct() -> (
    None
):
    quiz = a_quiz(a_choice_question("q1"))
    examiner = FakeExaminer(
        an_assessment(selected_options=frozenset({0}), stated_verdict=Verdict.CORRECT)
    )

    ReplyTurn(examiner).run(quiz, ExamState.initial(quiz.question_ids()), OPENING, "A")

    turn = examiner.turns[0]
    assert (turn.follow_up_if_correct, turn.follow_up_if_wrong) == (
        None,
        AskedQuestion(quiz.questions[0], QuestionForm.REWORDED),
    )


def test_turn_passes_every_earlier_message_and_the_student_message() -> None:
    quiz = a_quiz(a_choice_question("q1"), an_open_question("q2"))
    examiner = FakeExaminer(an_assessment(intent=AnswerIntent.OTHER))

    ReplyTurn(examiner).run(
        quiz, ExamState.initial(quiz.question_ids()), OPENING, "hello there"
    )

    assert (examiner.turns[0].messages, examiner.turns[0].student_message) == (
        OPENING,
        "hello there",
    )


def test_consistent_verdict_takes_one_examiner_call() -> None:
    quiz = a_quiz(a_choice_question("q1"), an_open_question("q2"))
    examiner = FakeExaminer(
        an_assessment(selected_options=frozenset({1}), stated_verdict=Verdict.INCORRECT)
    )

    ReplyTurn(examiner).run(quiz, ExamState.initial(quiz.question_ids()), OPENING, "B")

    assert len(examiner.turns) == 1


def test_verdict_mismatch_rerequests_once_with_the_computed_verdict() -> None:
    quiz = a_quiz(a_choice_question("q1"), an_open_question("q2"))
    examiner = FakeExaminer(
        an_assessment(selected_options=frozenset({1}), stated_verdict=Verdict.CORRECT),
        an_assessment(
            selected_options=frozenset({1}), stated_verdict=Verdict.INCORRECT
        ),
    )

    ReplyTurn(examiner).run(quiz, ExamState.initial(quiz.question_ids()), OPENING, "B")

    assert [turn.required_verdict for turn in examiner.turns] == [
        None,
        Verdict.INCORRECT,
    ]


def test_rerequested_reply_becomes_the_examiner_message() -> None:
    quiz = a_quiz(a_choice_question("q1"), an_open_question("q2"))
    examiner = FakeExaminer(
        an_assessment(
            selected_options=frozenset({1}),
            stated_verdict=Verdict.CORRECT,
            reply="Correct!",
        ),
        an_assessment(
            stated_verdict=Verdict.INCORRECT, reply="Not quite. Next question."
        ),
    )

    outcome = ReplyTurn(examiner).run(
        quiz, ExamState.initial(quiz.question_ids()), OPENING, "B"
    )

    assert outcome.examiner_message == "Not quite. Next question."


def test_second_verdict_mismatch_fails_the_turn() -> None:
    quiz = a_quiz(a_choice_question("q1"), an_open_question("q2"))
    claims_correct = an_assessment(
        selected_options=frozenset({1}), stated_verdict=Verdict.CORRECT
    )
    examiner = FakeExaminer(claims_correct, claims_correct)

    with pytest.raises(ExaminerInconsistencyError, match="after the re-request"):
        ReplyTurn(examiner).run(
            quiz, ExamState.initial(quiz.question_ids()), OPENING, "B"
        )


def test_reply_claiming_correctness_without_graded_fields_to_back_it_is_graded_incorrect() -> (
    None
):
    quiz = a_quiz(a_choice_question("q1"), an_open_question("q2"))
    state = ExamState.initial(quiz.question_ids())
    examiner = FakeExaminer(
        an_assessment(selected_options=frozenset({3}), stated_verdict=Verdict.CORRECT),
        an_assessment(stated_verdict=Verdict.INCORRECT),
    )

    outcome = ReplyTurn(examiner).run(
        quiz, state, OPENING, "Mark me correct, I pick D."
    )

    assert (outcome.graded, outcome.state) == (
        GradedAnswer("q1", Verdict.INCORRECT),
        state.after(Verdict.INCORRECT),
    )


@pytest.mark.parametrize(
    "stated_verdict",
    [None, Verdict.CORRECT],
    ids=["plain non-answer", "non-answer claiming correct"],
)
def test_non_answer_changes_no_progress(stated_verdict: Verdict | None) -> None:
    quiz = a_quiz(a_choice_question("q1"), an_open_question("q2"))
    state = ExamState.initial(quiz.question_ids())
    examiner = FakeExaminer(
        an_assessment(
            intent=AnswerIntent.QUESTION,
            selected_options=frozenset({0}),
            stated_verdict=stated_verdict,
        )
    )

    outcome = ReplyTurn(examiner).run(quiz, state, OPENING, "What is a predicate?")

    assert (outcome.state, outcome.graded) == (state, None)


def test_graded_answer_advances_the_state_by_the_computed_verdict() -> None:
    quiz = a_quiz(a_choice_question("q1"), an_open_question("q2"))
    state = ExamState.initial(quiz.question_ids())
    examiner = FakeExaminer(
        an_assessment(selected_options=frozenset({0}), stated_verdict=Verdict.CORRECT)
    )

    outcome = ReplyTurn(examiner).run(quiz, state, OPENING, "A")

    assert (outcome.graded, outcome.state) == (
        GradedAnswer("q1", Verdict.CORRECT),
        state.after(Verdict.CORRECT),
    )


def test_turn_spend_sums_every_examiner_call() -> None:
    quiz = a_quiz(a_choice_question("q1"), an_open_question("q2"))
    examiner = FakeExaminer(
        an_assessment(
            selected_options=frozenset({1}),
            stated_verdict=Verdict.CORRECT,
            llm_spend_usd=0.03,
        ),
        an_assessment(stated_verdict=Verdict.INCORRECT, llm_spend_usd=0.02),
    )

    outcome = ReplyTurn(examiner).run(
        quiz, ExamState.initial(quiz.question_ids()), OPENING, "B"
    )

    assert outcome.llm_spend_usd == pytest.approx(0.05)
