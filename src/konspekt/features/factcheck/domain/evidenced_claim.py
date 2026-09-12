from dataclasses import dataclass

from konspekt.features.factcheck.domain.evidence import Evidence


@dataclass(frozen=True, slots=True)
class EvidencedClaim:
    claim_text: str
    evidence: tuple[Evidence, ...]
