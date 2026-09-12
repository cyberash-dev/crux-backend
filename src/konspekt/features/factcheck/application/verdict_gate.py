from konspekt.features.factcheck.domain.claims import (
    ANNOTATION_REQUIRING_VERDICTS,
    EVIDENCE_REQUIRING_VERDICTS,
    CheckedClaim,
    ExtractedClaim,
    Verdict,
    VerificationOutcome,
)


def apply_outcome_gate(outcome: VerificationOutcome) -> VerificationOutcome:
    verdict = outcome.verdict
    annotation = outcome.annotation
    corrected_text = outcome.corrected_text
    if verdict in EVIDENCE_REQUIRING_VERDICTS:
        is_evidence_missing = (
            not outcome.sources
            or not set(outcome.sources) <= set(outcome.evidence_urls)
            or (verdict in ANNOTATION_REQUIRING_VERDICTS and annotation is None)
        )
        if is_evidence_missing:
            verdict = Verdict.UNVERIFIED
    if verdict not in ANNOTATION_REQUIRING_VERDICTS:
        annotation = None
    if verdict is not Verdict.DISPUTED:
        corrected_text = None
    return VerificationOutcome(
        verdict=verdict,
        sources=outcome.sources,
        annotation=annotation,
        corrected_text=corrected_text,
        evidence_urls=outcome.evidence_urls,
    )


def apply_verdict_gate(
    claim: ExtractedClaim,
    outcome: VerificationOutcome,
    claim_id: str = "",
) -> CheckedClaim:
    gated = apply_outcome_gate(outcome)
    return CheckedClaim(
        claim_text=claim.claim_text,
        span=claim.span,
        verdict=gated.verdict,
        sources=gated.sources,
        annotation=gated.annotation,
        claim_id=claim_id,
        corrected_text=gated.corrected_text,
    )
