from collections.abc import Mapping

from konspekt.features.quiz.domain.quiz import (
    QuestionType,
    Quiz,
    QuizQuestion,
    Rubric,
    RubricConcept,
)

_LEGACY_MCQ_TYPE = "mcq"


class QuizArtifactError(Exception):
    pass


def quiz_payload(quiz: Quiz) -> dict[str, object]:
    return {"questions": [_question_payload(question) for question in quiz.questions]}


def parse_quiz_payload(payload: Mapping[str, object]) -> Quiz:
    try:
        return Quiz(
            questions=tuple(
                _parse_question(raw_question) for raw_question in payload["questions"]
            )
        )
    except (KeyError, TypeError, ValueError) as error:
        raise QuizArtifactError(f"invalid quiz payload: {error!r}") from error


def rubric_payload(rubric: Rubric | None) -> dict[str, object] | None:
    if rubric is None:
        return None
    return {
        "max_points": rubric.max_points,
        "concepts": [
            {"description": concept.description, "points": concept.points}
            for concept in rubric.concepts
        ],
    }


def _question_payload(question: QuizQuestion) -> dict[str, object]:
    return {
        "question_id": question.question_id,
        "type": question.type.value,
        "prompt": question.prompt,
        "options": list(question.options) if question.options is not None else None,
        "correct_options": (
            list(question.correct_options) if question.correct_options is not None else None
        ),
        "model_answer": question.model_answer,
        "rubric": rubric_payload(question.rubric),
        "section_id": question.section_id,
    }


def _parse_question(raw_question: Mapping[str, object]) -> QuizQuestion:
    if "correct_option" in raw_question:
        raise QuizArtifactError(
            "field 'correct_option' is no longer accepted: "
            "use 'correct_options', a non-empty array of 0-based indices"
        )
    raw_options = raw_question["options"]
    raw_correct_options = raw_question["correct_options"]
    question_type = _parse_type(raw_question["type"], raw_correct_options)
    model_answer = raw_question["model_answer"]
    return QuizQuestion(
        question_id=raw_question["question_id"],
        type=question_type,
        prompt=raw_question["prompt"],
        section_id=raw_question["section_id"],
        options=tuple(raw_options) if raw_options is not None else None,
        correct_options=(
            tuple(raw_correct_options) if raw_correct_options is not None else None
        ),
        model_answer=model_answer,
        rubric=_parse_rubric(raw_question.get("rubric")),
    )


def _parse_type(raw_type: object, raw_correct_options: object) -> QuestionType:
    if raw_type == _LEGACY_MCQ_TYPE:
        unique_correct_count = (
            len(set(raw_correct_options)) if isinstance(raw_correct_options, list) else 0
        )
        if unique_correct_count >= 2:
            return QuestionType.MULTI_SELECT
        return QuestionType.SINGLE_CHOICE
    return QuestionType(raw_type)


def _parse_rubric(raw_rubric: object) -> Rubric | None:
    if raw_rubric is None:
        return None
    if not isinstance(raw_rubric, Mapping):
        raise QuizArtifactError(f"rubric must be an object or null, got {raw_rubric!r}")
    return Rubric(
        max_points=raw_rubric["max_points"],
        concepts=tuple(
            RubricConcept(description=concept["description"], points=concept["points"])
            for concept in raw_rubric["concepts"]
        ),
    )
