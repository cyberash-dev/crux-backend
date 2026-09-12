# @covers analysis:REQ-023
# @covers analysis:EXT-010
import pytest

from konspekt.features.notes.domain.notes import BlockKind, NoteBlock, NoteSection, Notes
from konspekt.features.quiz.application.generate_quiz import (
    QuizValidationError,
    generate_quiz,
)
from konspekt.features.quiz.domain.quiz import (
    QuestionType,
    Quiz,
    QuizConfig,
    QuizQuestion,
    Rubric,
    RubricConcept,
)
from konspekt.shared.timecode import TimeRange


class StubGeneration:
    def __init__(self, *quizzes: Quiz) -> None:
        self._pending_quizzes = list(quizzes)
        self.feedback_by_call: list[str | None] = []

    def generate(
        self, notes: Notes, config: QuizConfig, coverage_feedback: str | None = None
    ) -> Quiz:
        self.feedback_by_call.append(coverage_feedback)
        if len(self._pending_quizzes) > 1:
            return self._pending_quizzes.pop(0)
        return self._pending_quizzes[0]


def a_notes_with_sections(section_ids: list[str]) -> Notes:
    return Notes(
        title="Введение в термодинамику",
        language="ru",
        sections=tuple(
            NoteSection(
                section_id=section_id,
                title=f"Раздел {section_id}",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text="Текст раздела."),),
            )
            for section_id in section_ids
        ),
    )


def a_choice_question(
    question_id: str, section_id: str, correct_options: tuple[int, ...] = (0,)
) -> QuizQuestion:
    question_type = (
        QuestionType.SINGLE_CHOICE
        if len(correct_options) == 1
        else QuestionType.MULTI_SELECT
    )
    return QuizQuestion(
        question_id=question_id,
        type=question_type,
        prompt="Что сохраняется?",
        section_id=section_id,
        options=("Энергия", "Энтропия", "Температура", "Давление"),
        correct_options=correct_options,
    )


def an_open_question(question_id: str, section_id: str) -> QuizQuestion:
    return QuizQuestion(
        question_id=question_id,
        type=QuestionType.OPEN,
        prompt="Сформулируйте первое начало.",
        section_id=section_id,
        model_answer="Энергия изолированной системы сохраняется.",
        rubric=Rubric(
            max_points=3,
            concepts=(
                RubricConcept(description="Названо сохранение энергии", points=2),
                RubricConcept(description="Указана изолированная система", points=1),
            ),
        ),
    )


def a_full_coverage_quiz() -> Quiz:
    return Quiz(
        questions=(
            a_choice_question("q1", "s1"),
            a_choice_question("q2", "s1", correct_options=(0, 2)),
            a_choice_question("q3", "s2"),
            a_choice_question("q4", "s2"),
            a_choice_question("q5", "s3"),
            a_choice_question("q6", "s3"),
            a_choice_question("q7", "s1"),
            an_open_question("q8", "s2"),
            an_open_question("q9", "s3"),
            an_open_question("q10", "s1"),
        )
    )


def test_full_coverage_quiz_is_returned() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s3"])
    quiz = a_full_coverage_quiz()

    result = generate_quiz(notes, QuizConfig(), StubGeneration(quiz))

    assert result == quiz


def test_question_count_and_types_are_preserved() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s3"])

    result = generate_quiz(notes, QuizConfig(), StubGeneration(a_full_coverage_quiz()))

    types = [question.type for question in result.questions]
    assert len(result.questions) == 10
    assert types.count(QuestionType.SINGLE_CHOICE) == 6
    assert types.count(QuestionType.MULTI_SELECT) == 1
    assert types.count(QuestionType.OPEN) == 3


def test_multi_select_question_is_preserved() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s3"])

    result = generate_quiz(notes, QuizConfig(), StubGeneration(a_full_coverage_quiz()))

    assert result.questions[1].type is QuestionType.MULTI_SELECT
    assert result.questions[1].correct_options == (0, 2)


def test_uncovered_section_is_rejected_with_its_name() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s3"])
    questions = tuple(
        a_choice_question(f"q{index}", "s1" if index % 2 else "s2")
        for index in range(9)
    ) + (an_open_question("q9", "s1"),)

    with pytest.raises(QuizValidationError, match="s3"):
        generate_quiz(notes, QuizConfig(), StubGeneration(Quiz(questions=questions)))


def test_section_below_minimum_per_section_is_rejected() -> None:
    notes = a_notes_with_sections(["s1", "s2"])
    quiz = Quiz(
        questions=(
            a_choice_question("q1", "s1"),
            a_choice_question("q2", "s1"),
            a_choice_question("q3", "s2"),
        )
    )
    config = QuizConfig(minimum_total=3, questions_per_section=1, minimum_per_section=2)

    with pytest.raises(QuizValidationError, match="s2"):
        generate_quiz(notes, config, StubGeneration(quiz))


def test_total_below_target_is_rejected() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s3"])
    quiz = Quiz(
        questions=(
            a_choice_question("q1", "s1"),
            a_choice_question("q2", "s2"),
            a_choice_question("q3", "s3"),
        )
    )

    with pytest.raises(QuizValidationError, match="10"):
        generate_quiz(notes, QuizConfig(), StubGeneration(quiz))


def test_dangling_section_id_is_rejected_without_retry() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s3"])
    questions = a_full_coverage_quiz().questions[:9] + (an_open_question("q10", "s9"),)
    generation = StubGeneration(Quiz(questions=questions))

    with pytest.raises(QuizValidationError, match="s9"):
        generate_quiz(notes, QuizConfig(), generation)

    assert generation.feedback_by_call == [None]


def a_notes_with_subsections() -> Notes:
    return Notes(
        title="Введение в термодинамику",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Раздел s1",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text="Текст s1."),),
                subsections=(
                    NoteSection(
                        section_id="s1.1",
                        title="Подраздел s1.1",
                        source_spans=(TimeRange(30.0, 60.0),),
                        blocks=(NoteBlock(kind=BlockKind.PROSE, text="Текст s1.1."),),
                    ),
                ),
            ),
            NoteSection(
                section_id="s2",
                title="Раздел s2",
                source_spans=(TimeRange(60.0, 120.0),),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text="Текст s2."),),
            ),
        ),
    )


def test_subsection_question_credits_its_top_level_parent() -> None:
    notes = a_notes_with_subsections()
    questions = tuple(
        a_choice_question(f"q{index}", "s1.1" if index % 2 else "s2")
        for index in range(9)
    ) + (an_open_question("q9", "s1.1"),)
    generation = StubGeneration(Quiz(questions=questions))

    result = generate_quiz(notes, QuizConfig(), generation)

    assert result.questions == questions
    assert generation.feedback_by_call == [None]


def test_parent_uncovered_while_other_subsections_covered_is_rejected() -> None:
    notes = a_notes_with_subsections()
    questions = tuple(a_choice_question(f"q{index}", "s1.1") for index in range(10))
    generation = StubGeneration(Quiz(questions=questions))

    with pytest.raises(QuizValidationError, match="s2"):
        generate_quiz(notes, QuizConfig(), generation)


def test_dangling_id_inside_tree_is_rejected_without_retry() -> None:
    notes = a_notes_with_subsections()
    questions = tuple(
        a_choice_question(f"q{index}", "s1.1" if index % 2 else "s2")
        for index in range(9)
    ) + (a_choice_question("q9", "s9.1"),)
    generation = StubGeneration(Quiz(questions=questions))

    with pytest.raises(QuizValidationError, match="s9.1"):
        generate_quiz(notes, QuizConfig(), generation)

    assert generation.feedback_by_call == [None]


def a_quiz_ignoring_s6() -> Quiz:
    questions = tuple(
        a_choice_question(f"q{index}", "s1" if index % 2 else "s2")
        for index in range(9)
    ) + (an_open_question("q9", "s1"),)
    return Quiz(questions=questions)


def a_quiz_covering_s6() -> Quiz:
    questions = tuple(
        a_choice_question(f"q{index}", ("s1", "s2", "s6")[index % 3])
        for index in range(9)
    ) + (an_open_question("q9", "s6"),)
    return Quiz(questions=questions)


def test_uncovered_section_triggers_one_retry_with_feedback_naming_it() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s6"])
    generation = StubGeneration(a_quiz_ignoring_s6(), a_quiz_covering_s6())

    result = generate_quiz(notes, QuizConfig(), generation)

    assert result == a_quiz_covering_s6()
    assert len(generation.feedback_by_call) == 2
    assert generation.feedback_by_call[0] is None
    assert "s6" in generation.feedback_by_call[1]


def test_coverage_failure_on_retry_raises() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s6"])
    generation = StubGeneration(a_quiz_ignoring_s6(), a_quiz_ignoring_s6())

    with pytest.raises(QuizValidationError, match="s6"):
        generate_quiz(notes, QuizConfig(), generation)

    assert len(generation.feedback_by_call) == 2


def an_all_choice_quiz(section_ids: tuple[str, str, str]) -> Quiz:
    return Quiz(
        questions=tuple(
            a_choice_question(f"q{index}", section_ids[index % 3])
            for index in range(10)
        )
    )


def an_all_open_quiz(section_ids: tuple[str, str, str]) -> Quiz:
    return Quiz(
        questions=tuple(
            an_open_question(f"q{index}", section_ids[index % 3])
            for index in range(10)
        )
    )


def test_all_choice_quiz_triggers_retry_with_feedback_asking_for_open() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s3"])
    generation = StubGeneration(
        an_all_choice_quiz(("s1", "s2", "s3")), a_full_coverage_quiz()
    )

    result = generate_quiz(notes, QuizConfig(), generation)

    assert result == a_full_coverage_quiz()
    assert len(generation.feedback_by_call) == 2
    assert "open" in generation.feedback_by_call[1]


def test_all_open_quiz_triggers_retry_with_feedback_asking_for_choice() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s3"])
    generation = StubGeneration(
        an_all_open_quiz(("s1", "s2", "s3")), a_full_coverage_quiz()
    )

    result = generate_quiz(notes, QuizConfig(), generation)

    assert result == a_full_coverage_quiz()
    assert "choice" in generation.feedback_by_call[1]


def test_single_type_quiz_on_retry_is_accepted() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s3"])
    all_choice_quiz = an_all_choice_quiz(("s1", "s2", "s3"))
    generation = StubGeneration(all_choice_quiz, all_choice_quiz)

    result = generate_quiz(notes, QuizConfig(), generation)

    assert result == all_choice_quiz
    assert len(generation.feedback_by_call) == 2


def test_small_single_type_quiz_is_accepted_without_retry() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s3"])
    quiz = Quiz(
        questions=(
            a_choice_question("q1", "s1"),
            a_choice_question("q2", "s2"),
            a_choice_question("q3", "s3"),
        )
    )
    config = QuizConfig(minimum_total=3, questions_per_section=1, minimum_per_section=1)
    generation = StubGeneration(quiz)

    result = generate_quiz(notes, config, generation)

    assert result == quiz
    assert generation.feedback_by_call == [None]


def test_mix_feedback_is_appended_to_coverage_feedback() -> None:
    notes = a_notes_with_sections(["s1", "s2", "s6"])
    generation = StubGeneration(
        an_all_choice_quiz(("s1", "s2", "s2")), a_quiz_covering_s6()
    )

    result = generate_quiz(notes, QuizConfig(), generation)

    assert result == a_quiz_covering_s6()
    assert "s6" in generation.feedback_by_call[1]
    assert "open" in generation.feedback_by_call[1]
