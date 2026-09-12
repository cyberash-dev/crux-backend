from collections.abc import Mapping, Sequence
from typing import Any

from konspekt.features.factcheck.domain.claims import (
    ANNOTATION_REQUIRING_VERDICTS,
    EVIDENCE_REQUIRING_VERDICTS,
    CheckedClaim,
    Verdict,
    claim_id_for_position,
)
from konspekt.shared.timecode import TimeRange

_CLAIM_FIELDS = (
    "claim_text",
    "span_start_seconds",
    "span_end_seconds",
    "verdict",
    "sources",
    "annotation",
)


class ClaimsPayloadError(Exception):
    pass


def claims_payload(claims: Sequence[CheckedClaim]) -> dict[str, Any]:
    return {
        "claims": [
            {
                "claim_id": claim.claim_id,
                "claim_text": claim.claim_text,
                "span_start_seconds": claim.span.start_seconds,
                "span_end_seconds": claim.span.end_seconds,
                "verdict": claim.verdict.value,
                "sources": list(claim.sources),
                "annotation": claim.annotation,
                "corrected_text": claim.corrected_text,
            }
            for claim in claims
        ]
    }


def parse_claims_payload(payload: Mapping[str, Any]) -> tuple[CheckedClaim, ...]:
    if "claims" not in payload or not isinstance(payload["claims"], list):
        raise ClaimsPayloadError("payload is missing the claims array")
    return tuple(
        _parse_claim(raw_claim, position)
        for position, raw_claim in enumerate(payload["claims"])
    )


def _parse_claim(raw_claim: Mapping[str, Any], position: int) -> CheckedClaim:
    for field in _CLAIM_FIELDS:
        if field not in raw_claim:
            raise ClaimsPayloadError(f"claim is missing field {field!r}")
    try:
        verdict = Verdict(raw_claim["verdict"])
    except ValueError as error:
        raise ClaimsPayloadError(f"unknown verdict {raw_claim['verdict']!r}") from error
    sources = tuple(raw_claim["sources"])
    if verdict in EVIDENCE_REQUIRING_VERDICTS and not sources:
        raise ClaimsPayloadError(f"verdict {verdict.value!r} requires non-empty sources")
    annotation = raw_claim["annotation"]
    if verdict in ANNOTATION_REQUIRING_VERDICTS and annotation is None:
        raise ClaimsPayloadError(f"{verdict.value} claim requires an annotation")
    if verdict not in ANNOTATION_REQUIRING_VERDICTS and annotation is not None:
        raise ClaimsPayloadError(f"verdict {verdict.value!r} requires a null annotation")
    return CheckedClaim(
        claim_text=raw_claim["claim_text"],
        span=TimeRange(raw_claim["span_start_seconds"], raw_claim["span_end_seconds"]),
        verdict=verdict,
        sources=sources,
        annotation=annotation,
        claim_id=raw_claim.get("claim_id") or claim_id_for_position(position),
        corrected_text=raw_claim.get("corrected_text"),
    )
