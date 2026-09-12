from dataclasses import dataclass
from enum import StrEnum

from konspekt.shared.timecode import TimeRange


class Verdict(StrEnum):
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    MIXED = "mixed"
    UNVERIFIED = "unverified"


EVIDENCE_REQUIRING_VERDICTS = (Verdict.CONFIRMED, Verdict.DISPUTED, Verdict.MIXED)
ANNOTATION_REQUIRING_VERDICTS = (Verdict.DISPUTED, Verdict.MIXED)


def claim_id_for_position(position: int) -> str:
    return f"c_{position:03d}"


@dataclass(frozen=True, slots=True)
class ExtractedClaim:
    claim_text: str
    span: TimeRange


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    verdict: Verdict
    sources: tuple[str, ...]
    annotation: str | None
    corrected_text: str | None = None
    evidence_urls: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CheckedClaim:
    claim_text: str
    span: TimeRange
    verdict: Verdict
    sources: tuple[str, ...]
    annotation: str | None
    claim_id: str = ""
    corrected_text: str | None = None
