import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from konspekt.features.exam.domain.answer_grading import AnswerGrading
from konspekt.features.exam.domain.answer_intent import AnswerIntent
from konspekt.features.exam.domain.exam_question import ExamQuestion
from konspekt.features.exam.domain.exam_quiz import ExamQuiz
from konspekt.features.exam.domain.question_type import QuestionType
from konspekt.features.exam.domain.rubric import Rubric
from konspekt.features.exam.domain.rubric_concept import RubricConcept
from konspekt.features.exam.domain.verdict import Verdict
from konspekt.features.exam.domain.video_time_range import VideoTimeRange
from konspekt.features.exam.ports.outbound.examiner_assessment import ExaminerAssessment
from konspekt.features.exam.ports.outbound.examiner_model_error import (
    ExaminerModelError,
)
from konspekt.features.exam.ports.outbound.examiner_turn import ExaminerTurn

CHOICE_OPTIONS = (
    "Communication of the solution",
    "Testing on many inputs",
    "Optimizing constant factors",
    "Choosing a language",
)
LECTURE_NOTES = '# Algorithms\n\n## Course Introduction <a id="s1"></a>\n\nCommunication binds it all.\n'


def a_choice_question(
    question_id: str = "q1",
    question_type: QuestionType = QuestionType.SINGLE_CHOICE,
    correct_options: frozenset[int] = frozenset({0}),
) -> ExamQuestion:
    return ExamQuestion(
        question_id=question_id,
        type=question_type,
        prompt="Which activity binds solving, proving and arguing efficiency together?",
        options=CHOICE_OPTIONS,
        correct_options=correct_options,
        model_answer=None,
        rubric=None,
        time_range=VideoTimeRange(start_seconds=0.0, end_seconds=179.0),
        section_title="Course Introduction and Goals",
    )


def an_open_question(
    question_id: str = "q2", concept_points: Sequence[int] = (2, 1, 2)
) -> ExamQuestion:
    concepts = tuple(
        RubricConcept(description=f"concept {number}", points=points)
        for number, points in enumerate(concept_points, start=1)
    )
    return ExamQuestion(
        question_id=question_id,
        type=QuestionType.OPEN,
        prompt="Explain what a general problem with arbitrarily sized inputs is.",
        options=(),
        correct_options=frozenset(),
        model_answer="A problem whose inputs have unbounded size, specified by a predicate.",
        rubric=Rubric.with_mastery_threshold(sum(concept_points), concepts),
        time_range=VideoTimeRange(start_seconds=179.0, end_seconds=555.0),
        section_title="What Is a Computational Problem?",
    )


def a_quiz(*questions: ExamQuestion) -> ExamQuiz:
    return ExamQuiz(
        lecture_title="Introduction to Algorithms", language="en", questions=questions
    )


def an_assessment(
    intent: AnswerIntent = AnswerIntent.ANSWER,
    selected_options: frozenset[int] = frozenset(),
    covered_concepts: frozenset[int] = frozenset(),
    stated_verdict: Verdict | None = None,
    reply: str = "Examiner reply.",
    llm_spend_usd: float = 0.02,
) -> ExaminerAssessment:
    return ExaminerAssessment(
        intent=intent,
        grading=AnswerGrading(
            selected_options=selected_options, covered_concepts=covered_concepts
        ),
        stated_verdict=stated_verdict,
        reply=reply,
        llm_spend_usd=llm_spend_usd,
    )


class FakeExaminer:
    def __init__(self, *outcomes: ExaminerAssessment | ExaminerModelError) -> None:
        self._outcomes = list(outcomes)
        self.turns: list[ExaminerTurn] = []

    def assess(self, turn: ExaminerTurn) -> ExaminerAssessment:
        self.turns.append(turn)
        outcome = self._outcomes[len(self.turns) - 1]
        if isinstance(outcome, ExaminerModelError):
            raise outcome
        return outcome


def a_quiz_document(language: str = "en") -> dict[str, object]:
    return {
        "format_version": 2,
        "lecture_title": "Introduction to Algorithms",
        "language": language,
        "questions": [
            {
                "question_id": "q1",
                "type": "single_choice",
                "prompt": "Which activity binds solving, proving and arguing efficiency together?",
                "options": list(CHOICE_OPTIONS),
                "correct_options": [0],
                "model_answer": None,
                "rubric": None,
                "time_range": {"start_seconds": 0, "end_seconds": 179},
                "section_id": "s1",
                "section_title": "Course Introduction and Goals",
            },
            {
                "question_id": "q2",
                "type": "open",
                "prompt": "Explain what a general problem with arbitrarily sized inputs is.",
                "options": None,
                "correct_options": None,
                "model_answer": "A problem whose inputs have unbounded size.",
                "rubric": {
                    "max_points": 5,
                    "concepts": [
                        {"description": "inputs of unbounded size", "points": 2},
                        {"description": "predicate specification", "points": 1},
                        {"description": "fixed-size procedure", "points": 2},
                    ],
                },
                "time_range": {"start_seconds": 179, "end_seconds": 555},
                "section_id": "s2",
                "section_title": "What Is a Computational Problem?",
            },
        ],
    }


def a_state_document(
    queue: Sequence[tuple[str, str]], questions: Sequence[tuple[str, str, int]]
) -> dict[str, object]:
    return {
        "queue": [
            {"question_id": question_id, "form": form} for question_id, form in queue
        ],
        "questions": [
            {"question_id": question_id, "status": status, "attempts": attempts}
            for question_id, status, attempts in questions
        ],
    }


def a_reply_document(
    state: Mapping[str, object], student_message: str = "A"
) -> dict[str, object]:
    return {
        "kind": "reply",
        "state": state,
        "messages": [{"role": "examiner", "text": "Question 1 of 2: ..."}],
        "student_message": student_message,
    }


def an_exam_dir(
    tmp_path: Path,
    turn: Mapping[str, object],
    quiz: Mapping[str, object] | None = None,
) -> Path:
    (tmp_path / "konspekt.md").write_text(LECTURE_NOTES, encoding="utf-8")
    (tmp_path / "quiz.json").write_text(
        json.dumps(quiz or a_quiz_document()), encoding="utf-8"
    )
    (tmp_path / "turn.json").write_text(json.dumps(turn), encoding="utf-8")
    return tmp_path
