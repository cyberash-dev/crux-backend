from collections.abc import Sequence
from typing import Protocol

from konspekt.features.factcheck.domain.claims import (
    ExtractedClaim,
    VerificationOutcome,
)


class ClaimExtractionPort(Protocol):
    def extract_claims(
        self, core_text_with_timestamps: str, language: str
    ) -> list[ExtractedClaim]: ...


class ClaimVerificationPort(Protocol):
    def verify_batch(
        self, claim_texts: Sequence[str], language: str
    ) -> list[VerificationOutcome]: ...
