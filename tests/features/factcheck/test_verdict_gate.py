# @covers analysis:INV-021
# @covers analysis:REQ-022
# @covers analysis:DLT-032
# @covers analysis:CON-021
# @covers analysis:DLT-035
import pytest

from konspekt.features.factcheck.application.verdict_gate import apply_verdict_gate
from konspekt.features.factcheck.domain.claims import (
    ExtractedClaim,
    Verdict,
    VerificationOutcome,
)
from konspekt.shared.timecode import TimeRange


def a_claim(text: str = "Water boils at 100 C at sea level") -> ExtractedClaim:
    return ExtractedClaim(claim_text=text, span=TimeRange(10.0, 25.0))


def test_disputed_with_evidence_source_keeps_verdict_and_annotation() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.DISPUTED,
        sources=("https://doi.org/10.1000/xyz",),
        evidence_urls=("https://doi.org/10.1000/xyz",),
        annotation="Boiling point is 100 C only at standard pressure.",
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.DISPUTED
    assert checked.sources == ("https://doi.org/10.1000/xyz",)
    assert checked.annotation == "Boiling point is 100 C only at standard pressure."


def test_confirmed_with_evidence_source_keeps_verdict() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.CONFIRMED,
        sources=("https://pubmed.ncbi.nlm.nih.gov/1",),
        evidence_urls=("https://pubmed.ncbi.nlm.nih.gov/1",),
        annotation=None,
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.CONFIRMED
    assert checked.sources == ("https://pubmed.ncbi.nlm.nih.gov/1",)


def test_disputed_without_sources_is_downgraded_to_unverified() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.DISPUTED,
        sources=(),
        annotation="Contradicts the textbook.",
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.UNVERIFIED
    assert checked.annotation is None


def test_source_outside_the_evidence_is_downgraded_to_unverified() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.CONFIRMED,
        sources=("https://doi.org/10.9999/fabricated",),
        evidence_urls=("https://doi.org/10.1000/xyz",),
        annotation=None,
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.UNVERIFIED
    assert checked.annotation is None


def test_any_source_outside_the_evidence_downgrades_the_verdict() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.CONFIRMED,
        sources=("https://doi.org/10.1000/xyz", "https://invented.example.org/paper"),
        evidence_urls=("https://doi.org/10.1000/xyz",),
        annotation=None,
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.UNVERIFIED


def test_disputed_without_annotation_is_downgraded_to_unverified() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.DISPUTED,
        sources=("https://doi.org/10.1000/xyz",),
        evidence_urls=("https://doi.org/10.1000/xyz",),
        annotation=None,
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.UNVERIFIED
    assert checked.annotation is None


def test_confirmed_annotation_is_normalized_to_none() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.CONFIRMED,
        sources=("https://doi.org/10.1000/xyz",),
        evidence_urls=("https://doi.org/10.1000/xyz",),
        annotation="Extra remark the verifier attached.",
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.CONFIRMED
    assert checked.annotation is None


@pytest.mark.parametrize(
    "outcome",
    [
        VerificationOutcome(
            verdict=Verdict.DISPUTED,
            sources=("https://doi.org/10.1000/xyz",),
            evidence_urls=("https://doi.org/10.1000/xyz",),
            annotation="Disagrees with the source.",
        ),
        VerificationOutcome(verdict=Verdict.UNVERIFIED, sources=(), annotation=None),
    ],
)
def test_claim_text_is_byte_identical(outcome: VerificationOutcome) -> None:
    original_text = "Скорость света — 300 000 км/с"
    claim = a_claim(text=original_text)

    checked = apply_verdict_gate(claim, outcome)

    assert checked.claim_text.encode() == original_text.encode()
    assert checked.span == claim.span


def test_unverified_from_verifier_stays_unverified() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(verdict=Verdict.UNVERIFIED, sources=(), annotation=None)

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.UNVERIFIED
    assert checked.annotation is None


def test_mixed_with_evidence_source_keeps_verdict_and_annotation() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.MIXED,
        sources=("https://doi.org/10.1000/xyz",),
        evidence_urls=("https://doi.org/10.1000/xyz",),
        annotation="Верно только для стандартного давления.",
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.MIXED
    assert checked.annotation == "Верно только для стандартного давления."


def test_mixed_without_annotation_is_downgraded_to_unverified() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.MIXED,
        sources=("https://doi.org/10.1000/xyz",),
        evidence_urls=("https://doi.org/10.1000/xyz",),
        annotation=None,
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.UNVERIFIED
    assert checked.annotation is None


def test_mixed_without_sources_is_downgraded_to_unverified() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.MIXED,
        sources=(),
        annotation="Верно только для стандартного давления.",
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.UNVERIFIED
    assert checked.annotation is None


def test_mixed_with_source_outside_the_evidence_is_downgraded_to_unverified() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.MIXED,
        sources=("https://doi.org/10.9999/fabricated",),
        evidence_urls=("https://doi.org/10.1000/xyz",),
        annotation="Верно только для стандартного давления.",
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.UNVERIFIED
    assert checked.annotation is None


def test_disputed_keeps_corrected_text() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.DISPUTED,
        sources=("https://doi.org/10.1000/xyz",),
        evidence_urls=("https://doi.org/10.1000/xyz",),
        annotation="Расхождение с источником.",
        corrected_text="Скорость света — 299 792 км/с.",
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.corrected_text == "Скорость света — 299 792 км/с."


@pytest.mark.parametrize(
    "outcome",
    [
        VerificationOutcome(
            verdict=Verdict.CONFIRMED,
            sources=("https://doi.org/10.1000/xyz",),
            evidence_urls=("https://doi.org/10.1000/xyz",),
            annotation=None,
            corrected_text="Лишняя правка.",
        ),
        VerificationOutcome(
            verdict=Verdict.MIXED,
            sources=("https://doi.org/10.1000/xyz",),
            evidence_urls=("https://doi.org/10.1000/xyz",),
            annotation="Верно в узком смысле.",
            corrected_text="Лишняя правка.",
        ),
        VerificationOutcome(
            verdict=Verdict.UNVERIFIED,
            sources=(),
            annotation=None,
            corrected_text="Лишняя правка.",
        ),
    ],
    ids=["confirmed", "mixed", "unverified"],
)
def test_corrected_text_is_nulled_for_non_disputed(outcome: VerificationOutcome) -> None:
    claim = a_claim()

    checked = apply_verdict_gate(claim, outcome)

    assert checked.corrected_text is None


def test_downgraded_disputed_loses_corrected_text() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(
        verdict=Verdict.DISPUTED,
        sources=(),
        annotation="Расхождение с источником.",
        corrected_text="Скорость света — 299 792 км/с.",
    )

    checked = apply_verdict_gate(claim, outcome)

    assert checked.verdict == Verdict.UNVERIFIED
    assert checked.corrected_text is None


def test_claim_id_is_passed_through_to_the_checked_claim() -> None:
    claim = a_claim()
    outcome = VerificationOutcome(verdict=Verdict.UNVERIFIED, sources=(), annotation=None)

    checked = apply_verdict_gate(claim, outcome, claim_id="c_007")

    assert checked.claim_id == "c_007"
