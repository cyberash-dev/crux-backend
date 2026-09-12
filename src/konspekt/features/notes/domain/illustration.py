from dataclasses import dataclass
from enum import StrEnum


class CandidateFit(StrEnum):
    PERFECT = "perfect"
    SUITABLE = "suitable"
    UNSUITABLE = "unsuitable"


PERFECT_SCORE_THRESHOLD = 85
SUITABLE_SCORE_THRESHOLD = 50


@dataclass(frozen=True, slots=True)
class CandidateAssessment:
    score: int

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError("assessment score must be within 0..100")

    @property
    def fit(self) -> CandidateFit:
        if self.score >= PERFECT_SCORE_THRESHOLD:
            return CandidateFit.PERFECT
        if self.score >= SUITABLE_SCORE_THRESHOLD:
            return CandidateFit.SUITABLE
        return CandidateFit.UNSUITABLE


@dataclass(frozen=True, slots=True)
class IllustrationRequest:
    purpose: str
    search_query: str
    generation_prompt: str
    insert_index: int

    def __post_init__(self) -> None:
        if not self.purpose.strip() or not self.search_query.strip():
            raise ValueError("illustration request requires purpose and search_query")
        if not self.generation_prompt.strip():
            raise ValueError("illustration request requires generation_prompt")
        if self.insert_index < 0:
            raise ValueError("insert_index must be non-negative")


@dataclass(frozen=True, slots=True)
class IllustrationConfig:
    max_requests_per_section: int = 1
    commons_candidates: int = 6
    allow_generation: bool = False
    max_generated_per_lecture: int = 8
    max_workers: int = 3


GENERATED_CAPTION_LABEL_BY_LANGUAGE = {
    "ru": "Иллюстрация сгенерирована ИИ",
    "en": "AI-generated illustration",
}
