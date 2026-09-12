from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from konspekt.features.factcheck.application.verdict_gate import apply_verdict_gate
from konspekt.features.factcheck.domain.claims import (
    CheckedClaim,
    ExtractedClaim,
    Verdict,
    VerificationOutcome,
    claim_id_for_position,
)
from konspekt.features.factcheck.ports.outbound.factcheck_llm import (
    ClaimExtractionPort,
    ClaimVerificationPort,
)
from konspekt.features.factcheck.ports.outbound.verification_fatal_errors import (
    VERIFICATION_FATAL_ERRORS,
)

BATCH_SIZE = 5


def check_claims(
    core_text_with_timestamps: str,
    language: str,
    extraction_port: ClaimExtractionPort,
    verification_port: ClaimVerificationPort,
    max_workers: int = 4,
) -> list[CheckedClaim]:
    extracted = extraction_port.extract_claims(core_text_with_timestamps, language)
    if not extracted:
        return []
    batches = [
        extracted[batch_start : batch_start + BATCH_SIZE]
        for batch_start in range(0, len(extracted), BATCH_SIZE)
    ]
    with ThreadPoolExecutor(max_workers=min(max_workers, len(batches))) as pool:
        outcome_batches = list(
            pool.map(
                lambda batch: _verify_batch_or_unverified(
                    batch, verification_port, language
                ),
                batches,
            )
        )
    outcomes = [outcome for outcome_batch in outcome_batches for outcome in outcome_batch]
    return [
        apply_verdict_gate(
            claim,
            _with_deduplicated_sources(outcome),
            claim_id=claim_id_for_position(position),
        )
        for position, (claim, outcome) in enumerate(zip(extracted, outcomes, strict=True))
    ]


def _with_deduplicated_sources(outcome: VerificationOutcome) -> VerificationOutcome:
    return replace(outcome, sources=tuple(dict.fromkeys(outcome.sources)))


def _verify_batch_or_unverified(
    batch: Sequence[ExtractedClaim],
    verification_port: ClaimVerificationPort,
    language: str,
) -> list[VerificationOutcome]:
    try:
        outcomes = verification_port.verify_batch(
            [claim.claim_text for claim in batch], language
        )
    except VERIFICATION_FATAL_ERRORS:
        raise
    except Exception:
        # per analysis:CON-021 error_taxonomy: a failed verification keeps
        # the claims as unverified and the stage continues
        return _all_unverified(len(batch))
    if len(outcomes) != len(batch):
        return _all_unverified(len(batch))
    return outcomes


def _all_unverified(claim_count: int) -> list[VerificationOutcome]:
    return [
        VerificationOutcome(verdict=Verdict.UNVERIFIED, sources=(), annotation=None)
        for _ in range(claim_count)
    ]
