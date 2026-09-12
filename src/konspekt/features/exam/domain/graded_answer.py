from dataclasses import dataclass

from konspekt.features.exam.domain.verdict import Verdict


@dataclass(frozen=True, slots=True)
class GradedAnswer:
    question_id: str
    verdict: Verdict
