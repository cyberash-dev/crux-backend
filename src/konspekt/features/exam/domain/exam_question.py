from dataclasses import dataclass

from konspekt.features.exam.domain.question_type import QuestionType
from konspekt.features.exam.domain.rubric import Rubric
from konspekt.features.exam.domain.video_time_range import VideoTimeRange

OPTION_LETTERS = ("A", "B", "C", "D")


@dataclass(frozen=True, slots=True)
class ExamQuestion:
    question_id: str
    type: QuestionType
    prompt: str
    options: tuple[str, ...]
    correct_options: frozenset[int]
    model_answer: str | None
    rubric: Rubric | None
    time_range: VideoTimeRange
    section_title: str

    def lettered_options(self) -> tuple[tuple[str, str], ...]:
        return tuple(zip(OPTION_LETTERS, self.options, strict=False))

    def correct_option_texts(self) -> tuple[str, ...]:
        return tuple(self.options[index] for index in sorted(self.correct_options))
