from dataclasses import dataclass
from enum import StrEnum

CHOICE_OPTION_COUNT = 4
MULTI_SELECT_MINIMUM_CORRECT = 2


class QuestionType(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTI_SELECT = "multi_select"
    OPEN = "open"


@dataclass(frozen=True, slots=True)
class RubricConcept:
    description: str
    points: int

    def __post_init__(self) -> None:
        if self.points < 1:
            raise ValueError("rubric concept points must be >= 1")


@dataclass(frozen=True, slots=True)
class Rubric:
    max_points: int
    concepts: tuple[RubricConcept, ...]

    def __post_init__(self) -> None:
        if not self.concepts:
            raise ValueError("rubric requires at least one concept")
        points_total = sum(concept.points for concept in self.concepts)
        if points_total != self.max_points:
            raise ValueError(
                f"rubric concept points sum to {points_total}, "
                f"expected max_points {self.max_points}"
            )


@dataclass(frozen=True, slots=True)
class QuizQuestion:
    question_id: str
    type: QuestionType
    prompt: str
    section_id: str
    options: tuple[str, ...] | None = None
    correct_options: tuple[int, ...] | None = None
    model_answer: str | None = None
    rubric: Rubric | None = None

    def __post_init__(self) -> None:
        if self.type is QuestionType.OPEN:
            self._validate_open()
        else:
            self._validate_choice()

    def _validate_choice(self) -> None:
        if self.options is None or len(self.options) != CHOICE_OPTION_COUNT:
            raise ValueError(
                f"{self.type.value} question requires exactly "
                f"{CHOICE_OPTION_COUNT} options"
            )
        if not self.correct_options or len(set(self.correct_options)) != len(
            self.correct_options
        ):
            raise ValueError(
                f"{self.type.value} question requires a non-empty set of "
                "unique correct_options"
            )
        if any(not 0 <= option < CHOICE_OPTION_COUNT for option in self.correct_options):
            raise ValueError("correct_options must be indices in range 0..3")
        if self.type is QuestionType.SINGLE_CHOICE and len(self.correct_options) != 1:
            raise ValueError("single_choice question requires exactly one correct option")
        if (
            self.type is QuestionType.MULTI_SELECT
            and len(self.correct_options) < MULTI_SELECT_MINIMUM_CORRECT
        ):
            raise ValueError(
                "multi_select question requires at least two correct_options"
            )
        if self.model_answer is not None:
            raise ValueError(f"{self.type.value} question must not carry model_answer")
        if self.rubric is not None:
            raise ValueError(f"{self.type.value} question must not carry rubric")

    def _validate_open(self) -> None:
        if self.model_answer is None:
            raise ValueError("open question requires model_answer")
        if self.rubric is None:
            raise ValueError("open question requires rubric")
        if self.options is not None or self.correct_options is not None:
            raise ValueError("open question must not carry options or correct_options")


@dataclass(frozen=True, slots=True)
class Quiz:
    questions: tuple[QuizQuestion, ...]


@dataclass(frozen=True, slots=True)
class QuizConfig:
    minimum_total: int = 10
    questions_per_section: int = 2
    minimum_per_section: int = 1

    def target_for(self, section_count: int) -> int:
        return max(self.minimum_total, self.questions_per_section * section_count)
