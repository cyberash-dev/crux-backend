from collections.abc import Mapping
from dataclasses import dataclass

from konspekt.features.exam.domain.exam_quiz import ExamQuiz
from konspekt.features.exam.domain.question_type import QuestionType


@dataclass(frozen=True, slots=True)
class _OpeningTexts:
    introduction: str
    question_heading: str
    answer_hints: Mapping[QuestionType, str]


_ENGLISH = _OpeningTexts(
    introduction=(
        'Exam on the lecture "{title}".\n'
        "{total} questions. The exam goes on until every question is answered correctly: "
        "a question answered wrong comes back later in new words."
    ),
    question_heading="Question 1 of {total}:",
    answer_hints={
        QuestionType.SINGLE_CHOICE: "Choose one option.",
        QuestionType.MULTI_SELECT: "Choose every correct option.",
        QuestionType.OPEN: "Answer in your own words.",
    },
)
_RUSSIAN = _OpeningTexts(
    introduction=(
        "Экзамен по лекции «{title}».\n"
        "Вопросов: {total}. Экзамен идёт, пока на каждый вопрос не будет дан верный ответ: "
        "вопрос с неверным ответом вернётся позже в новой формулировке."
    ),
    question_heading="Вопрос 1 из {total}:",
    answer_hints={
        QuestionType.SINGLE_CHOICE: "Выберите один вариант.",
        QuestionType.MULTI_SELECT: "Выберите все верные варианты.",
        QuestionType.OPEN: "Ответьте своими словами.",
    },
)
_TEXTS_BY_LANGUAGE: Mapping[str, _OpeningTexts] = {"en": _ENGLISH, "ru": _RUSSIAN}


def opening_message(quiz: ExamQuiz) -> str:
    texts = _TEXTS_BY_LANGUAGE.get(quiz.language, _ENGLISH)
    total = len(quiz.questions)
    first_question = quiz.questions[0]
    return "\n".join(
        [
            texts.introduction.format(title=quiz.lecture_title, total=total),
            "",
            texts.question_heading.format(total=total),
            first_question.prompt,
            *(
                f"{letter}. {text}"
                for letter, text in first_question.lettered_options()
            ),
            texts.answer_hints[first_question.type],
        ]
    )
