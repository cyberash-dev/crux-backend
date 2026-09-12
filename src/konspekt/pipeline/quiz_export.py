from typing import Any

from konspekt.features.notes.domain.notes import NoteSection, Notes
from konspekt.features.quiz.application.artifact import rubric_payload
from konspekt.features.quiz.domain.quiz import Quiz, QuizQuestion

EXPORT_FORMAT_VERSION = 2


def build_quiz_export(quiz: Quiz, notes: Notes) -> dict[str, Any]:
    sections_by_id = {section.section_id: section for section in notes.all_sections()}
    return {
        "format_version": EXPORT_FORMAT_VERSION,
        "lecture_title": notes.title,
        "language": notes.language,
        "questions": [
            _question_export(question, sections_by_id) for question in quiz.questions
        ],
    }


def _question_export(
    question: QuizQuestion, sections_by_id: dict[str, NoteSection]
) -> dict[str, Any]:
    if question.section_id not in sections_by_id:
        raise ValueError(f"question {question.question_id} references unknown section "
                         f"{question.section_id!r}")
    section = sections_by_id[question.section_id]
    return {
        "question_id": question.question_id,
        "type": question.type.value,
        "prompt": question.prompt,
        "options": list(question.options) if question.options is not None else None,
        "correct_options": list(question.correct_options)
        if question.correct_options is not None
        else None,
        "model_answer": question.model_answer,
        "rubric": rubric_payload(question.rubric),
        "time_range": _time_range_export(section),
        "section_id": question.section_id,
        "section_title": section.title,
    }


def _time_range_export(section: NoteSection) -> dict[str, float]:
    return {
        "start_seconds": section.source_spans[0].start_seconds,
        "end_seconds": section.source_spans[-1].end_seconds,
    }
