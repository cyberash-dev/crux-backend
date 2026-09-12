from konspekt.features.notes.domain.notes import Notes
from konspekt.features.quiz.domain.quiz import QuestionType, Quiz, QuizConfig
from konspekt.features.quiz.ports.outbound.quiz_llm import QuizGenerationPort

MIX_RULE_MINIMUM_QUESTIONS = 3


class QuizValidationError(Exception):
    pass


class QuizCoverageError(QuizValidationError):
    pass


def generate_quiz(notes: Notes, config: QuizConfig, generation: QuizGenerationPort) -> Quiz:
    first_quiz = generation.generate(notes, config)
    feedback_parts: list[str] = []
    try:
        _validated(first_quiz, notes, config)
    except QuizCoverageError as coverage_error:
        feedback_parts.append(str(coverage_error))
    mix_feedback = _type_mix_feedback(first_quiz)
    if mix_feedback is not None:
        feedback_parts.append(mix_feedback)
    if not feedback_parts:
        return first_quiz
    retry_quiz = generation.generate(
        notes, config, coverage_feedback="; ".join(feedback_parts)
    )
    return _validated(retry_quiz, notes, config)


def _type_mix_feedback(quiz: Quiz) -> str | None:
    if len(quiz.questions) <= MIX_RULE_MINIMUM_QUESTIONS:
        return None
    has_open = any(
        question.type is QuestionType.OPEN for question in quiz.questions
    )
    has_choice = any(
        question.type is not QuestionType.OPEN for question in quiz.questions
    )
    if has_open and has_choice:
        return None
    if not has_open:
        return "all questions are choice questions; include at least one 'open' question"
    return (
        "all questions are open questions; include at least one choice question "
        "(single_choice or multi_select)"
    )


def _validated(quiz: Quiz, notes: Notes, config: QuizConfig) -> Quiz:
    known_section_ids = {section.section_id for section in notes.all_sections()}
    for question in quiz.questions:
        if question.section_id not in known_section_ids:
            raise QuizValidationError(
                f"question {question.question_id!r} references unknown section "
                f"{question.section_id!r}"
            )
    question_count_by_top_section = {
        section.section_id: 0 for section in notes.sections
    }
    for question in quiz.questions:
        top_section_id = notes.owning_top_section_id(question.section_id)
        if top_section_id is not None:
            question_count_by_top_section[top_section_id] += 1
    undercovered_section_ids = sorted(
        section_id
        for section_id, question_count in question_count_by_top_section.items()
        if question_count < config.minimum_per_section
    )
    if undercovered_section_ids:
        raise QuizCoverageError(
            f"sections {', '.join(undercovered_section_ids)} have fewer than "
            f"{config.minimum_per_section} question(s)"
        )
    target_count = config.target_for(len(notes.sections))
    if len(quiz.questions) < target_count:
        raise QuizCoverageError(
            f"quiz has {len(quiz.questions)} questions, target is {target_count}"
        )
    return quiz
