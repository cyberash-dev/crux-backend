from konspekt.features.exam.adapters.inbound.exam_input_error import ExamInputError
from konspekt.features.exam.adapters.inbound.json_fields import (
    json_count,
    json_enum,
    json_list,
    json_object,
    json_seconds,
    json_text,
)
from konspekt.features.exam.domain.exam_question import OPTION_LETTERS, ExamQuestion
from konspekt.features.exam.domain.exam_quiz import ExamQuiz
from konspekt.features.exam.domain.question_type import QuestionType
from konspekt.features.exam.domain.rubric import Rubric
from konspekt.features.exam.domain.rubric_concept import RubricConcept
from konspekt.features.exam.domain.video_time_range import VideoTimeRange

_FORMAT_VERSION = 2


def parse_quiz(raw_quiz: object) -> ExamQuiz:
    quiz_fields = json_object(raw_quiz, "quiz")
    if quiz_fields.get("format_version") != _FORMAT_VERSION:
        raise ExamInputError(f"quiz format_version must be {_FORMAT_VERSION}")
    questions = tuple(
        _question(raw)
        for raw in json_list(quiz_fields.get("questions"), "quiz questions")
    )
    question_ids = [question.question_id for question in questions]
    if not questions or len(set(question_ids)) != len(question_ids):
        raise ExamInputError(
            "quiz questions must be non-empty with unique question_id values"
        )
    return ExamQuiz(
        lecture_title=json_text(quiz_fields.get("lecture_title"), "quiz lecture_title"),
        language=json_text(quiz_fields.get("language"), "quiz language"),
        questions=questions,
    )


def _question(raw_question: object) -> ExamQuestion:
    fields = json_object(raw_question, "quiz question")
    question_id = json_text(fields.get("question_id"), "quiz question_id")
    label = f"question {question_id}"
    question_type = json_enum(QuestionType, fields.get("type"), f"{label} type")
    is_open = question_type is QuestionType.OPEN
    return ExamQuestion(
        question_id=question_id,
        type=question_type,
        prompt=json_text(fields.get("prompt"), f"{label} prompt"),
        options=() if is_open else _options(fields.get("options"), label),
        correct_options=frozenset()
        if is_open
        else _correct_options(fields.get("correct_options"), label),
        model_answer=_model_answer(fields.get("model_answer"), label),
        rubric=_rubric(fields.get("rubric"), label) if is_open else None,
        time_range=_time_range(fields.get("time_range"), label),
        section_title=json_text(fields.get("section_title"), f"{label} section_title"),
    )


def _options(raw_options: object, label: str) -> tuple[str, ...]:
    options = tuple(
        json_text(raw, f"{label} option")
        for raw in json_list(raw_options, f"{label} options")
    )
    if len(options) != len(OPTION_LETTERS):
        raise ExamInputError(
            f"{label} must carry exactly {len(OPTION_LETTERS)} options"
        )
    return options


def _correct_options(raw_indices: object, label: str) -> frozenset[int]:
    indices = [
        json_count(raw, f"{label} correct option", minimum=0)
        for raw in json_list(raw_indices, label)
    ]
    if (
        not indices
        or len(set(indices)) != len(indices)
        or max(indices) >= len(OPTION_LETTERS)
    ):
        raise ExamInputError(
            f"{label} correct_options must be unique option indices 0..3"
        )
    return frozenset(indices)


def _model_answer(raw_answer: object, label: str) -> str | None:
    return (
        None if raw_answer is None else json_text(raw_answer, f"{label} model_answer")
    )


def _rubric(raw_rubric: object, label: str) -> Rubric:
    fields = json_object(raw_rubric, f"{label} rubric")
    max_points = json_count(
        fields.get("max_points"), f"{label} rubric max_points", minimum=1
    )
    concepts = tuple(
        _concept(raw, label)
        for raw in json_list(fields.get("concepts"), f"{label} rubric concepts")
    )
    if sum(concept.points for concept in concepts) != max_points:
        raise ExamInputError(f"{label} rubric concept points must sum to max_points")
    return Rubric.with_mastery_threshold(max_points, concepts)


def _concept(raw_concept: object, label: str) -> RubricConcept:
    fields = json_object(raw_concept, f"{label} rubric concept")
    return RubricConcept(
        description=json_text(
            fields.get("description"), f"{label} concept description"
        ),
        points=json_count(fields.get("points"), f"{label} concept points", minimum=1),
    )


def _time_range(raw_range: object, label: str) -> VideoTimeRange:
    fields = json_object(raw_range, f"{label} time_range")
    start_seconds = json_seconds(fields.get("start_seconds"), f"{label} start_seconds")
    end_seconds = json_seconds(fields.get("end_seconds"), f"{label} end_seconds")
    if end_seconds < start_seconds:
        raise ExamInputError(f"{label} time_range ends before it starts")
    return VideoTimeRange(start_seconds, end_seconds)
