# @covers output:CON-031
# @covers output:DLT-035
import pytest

from konspekt.features.notes.domain.notes import BlockKind, NoteBlock, NoteSection, Notes
from konspekt.features.quiz.domain.quiz import (
    QuestionType,
    Quiz,
    QuizQuestion,
    Rubric,
    RubricConcept,
)
from konspekt.pipeline.quiz_export import build_quiz_export
from konspekt.shared.timecode import TimeRange


def a_notes() -> Notes:
    return Notes(
        title="Анатомия как наука",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Определение анатомии",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text="текст"),),
            ),
        ),
    )


def a_rubric() -> Rubric:
    return Rubric(
        max_points=3,
        concepts=(
            RubricConcept(description="Названо строение организма", points=2),
            RubricConcept(description="Приведён пример", points=1),
        ),
    )


def test_export_carries_questions_with_section_titles() -> None:
    quiz = Quiz(
        questions=(
            QuizQuestion(
                question_id="q1",
                type=QuestionType.MULTI_SELECT,
                prompt="Что изучает анатомия?",
                section_id="s1",
                options=("а", "б", "в", "г"),
                correct_options=(0, 2),
            ),
            QuizQuestion(
                question_id="q2",
                type=QuestionType.OPEN,
                prompt="Объясните.",
                section_id="s1",
                model_answer="Строение организма.",
                rubric=a_rubric(),
            ),
        )
    )

    export = build_quiz_export(quiz, a_notes())

    assert export["format_version"] == 2
    assert export["lecture_title"] == "Анатомия как наука"
    assert export["language"] == "ru"
    first, second = export["questions"]
    assert first == {
        "question_id": "q1",
        "type": "multi_select",
        "prompt": "Что изучает анатомия?",
        "options": ["а", "б", "в", "г"],
        "correct_options": [0, 2],
        "model_answer": None,
        "rubric": None,
        "time_range": {"start_seconds": 0.0, "end_seconds": 60.0},
        "section_id": "s1",
        "section_title": "Определение анатомии",
    }
    assert second["type"] == "open"
    assert second["correct_options"] is None
    assert second["model_answer"] == "Строение организма."


def test_export_serializes_single_choice_type_value() -> None:
    quiz = Quiz(
        questions=(
            QuizQuestion(
                question_id="q1",
                type=QuestionType.SINGLE_CHOICE,
                prompt="?",
                section_id="s1",
                options=("а", "б", "в", "г"),
                correct_options=(1,),
            ),
        )
    )

    export = build_quiz_export(quiz, a_notes())

    assert export["questions"][0]["type"] == "single_choice"


def test_export_passes_open_question_rubric_through() -> None:
    quiz = Quiz(
        questions=(
            QuizQuestion(
                question_id="q1",
                type=QuestionType.OPEN,
                prompt="Объясните.",
                section_id="s1",
                model_answer="Строение организма.",
                rubric=a_rubric(),
            ),
        )
    )

    export = build_quiz_export(quiz, a_notes())

    assert export["questions"][0]["rubric"] == {
        "max_points": 3,
        "concepts": [
            {"description": "Названо строение организма", "points": 2},
            {"description": "Приведён пример", "points": 1},
        ],
    }


def test_export_derives_time_range_from_first_and_last_source_span() -> None:
    notes = Notes(
        title="t",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Раздел",
                source_spans=(
                    TimeRange(30.0, 90.0),
                    TimeRange(120.0, 180.0),
                    TimeRange(240.0, 300.0),
                ),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text="x"),),
            ),
        ),
    )
    quiz = Quiz(
        questions=(
            QuizQuestion(
                question_id="q1",
                type=QuestionType.OPEN,
                prompt="?",
                section_id="s1",
                model_answer="a",
                rubric=a_rubric(),
            ),
        )
    )

    export = build_quiz_export(quiz, notes)

    assert export["questions"][0]["time_range"] == {
        "start_seconds": 30.0,
        "end_seconds": 300.0,
    }


def test_export_rejects_question_with_unknown_section() -> None:
    quiz = Quiz(
        questions=(
            QuizQuestion(
                question_id="q1",
                type=QuestionType.OPEN,
                prompt="?",
                section_id="missing",
                model_answer="a",
                rubric=a_rubric(),
            ),
        )
    )

    with pytest.raises(ValueError, match="missing"):
        build_quiz_export(quiz, a_notes())


def test_export_resolves_subsection_titles_and_spans() -> None:
    notes = Notes(
        title="t",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Раздел",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text="x"),),
                subsections=(
                    NoteSection(
                        section_id="s1.1",
                        title="Подраздел",
                        source_spans=(TimeRange(10.0, 30.0),),
                        blocks=(NoteBlock(kind=BlockKind.PROSE, text="y"),),
                    ),
                ),
            ),
        ),
    )
    quiz = Quiz(
        questions=(
            QuizQuestion(
                question_id="q1",
                type=QuestionType.OPEN,
                prompt="?",
                section_id="s1.1",
                model_answer="a",
                rubric=a_rubric(),
            ),
        )
    )

    export = build_quiz_export(quiz, notes)

    assert export["questions"][0]["section_title"] == "Подраздел"
    assert export["questions"][0]["time_range"] == {
        "start_seconds": 10.0,
        "end_seconds": 30.0,
    }
