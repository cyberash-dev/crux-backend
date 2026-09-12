from collections.abc import Sequence
from typing import Protocol

from konspekt.features.factcheck.domain.evidenced_claim import EvidencedClaim
from konspekt.features.factcheck.domain.judged_claim import JudgedClaim


class EvidenceJudgePort(Protocol):
    def judge_batch(
        self, claims: Sequence[EvidencedClaim], language: str
    ) -> list[JudgedClaim]: ...
