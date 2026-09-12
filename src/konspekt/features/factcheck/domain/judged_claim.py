from dataclasses import dataclass

from konspekt.features.factcheck.domain.claims import Verdict


@dataclass(frozen=True, slots=True)
class JudgedClaim:
    verdict: Verdict
    cited_evidence_numbers: tuple[int, ...]
    annotation: str | None
    corrected_text: str | None
