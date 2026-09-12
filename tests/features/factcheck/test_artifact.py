# @covers analysis:CON-021
# @covers analysis:DLT-032
import pytest

from konspekt.features.factcheck.application.artifact import (
    ClaimsPayloadError,
    claims_payload,
    parse_claims_payload,
)
from konspekt.features.factcheck.domain.claims import CheckedClaim, Verdict
from konspekt.shared.timecode import TimeRange


def a_checked_claim(
    verdict: Verdict = Verdict.CONFIRMED,
    sources: tuple[str, ...] = ("https://doi.org/10.1000/xyz",),
    annotation: str | None = None,
    claim_id: str = "c_000",
    corrected_text: str | None = None,
) -> CheckedClaim:
    return CheckedClaim(
        claim_text="Water boils at 100 C at sea level",
        span=TimeRange(10.0, 25.5),
        verdict=verdict,
        sources=sources,
        annotation=annotation,
        claim_id=claim_id,
        corrected_text=corrected_text,
    )


def test_payload_round_trips() -> None:
    claims = [
        a_checked_claim(),
        a_checked_claim(
            verdict=Verdict.DISPUTED,
            sources=("https://pubmed.ncbi.nlm.nih.gov/1", "10.1000/second"),
            annotation="The lecturer's figure disagrees with the source.",
            claim_id="c_001",
            corrected_text="Water boils at 100 C only at standard pressure.",
        ),
        a_checked_claim(
            verdict=Verdict.MIXED,
            annotation="Correct only under a narrow reading.",
            claim_id="c_002",
        ),
        a_checked_claim(
            verdict=Verdict.UNVERIFIED, sources=(), annotation=None, claim_id="c_003"
        ),
    ]

    restored = parse_claims_payload(claims_payload(claims))

    assert restored == tuple(claims)


def test_payload_uses_contract_field_names() -> None:
    payload = claims_payload([a_checked_claim()])

    assert payload["claims"] == [
        {
            "claim_id": "c_000",
            "claim_text": "Water boils at 100 C at sea level",
            "span_start_seconds": 10.0,
            "span_end_seconds": 25.5,
            "verdict": "confirmed",
            "sources": ["https://doi.org/10.1000/xyz"],
            "annotation": None,
            "corrected_text": None,
        }
    ]


def a_raw_claim(**overrides: object) -> dict[str, object]:
    raw_claim: dict[str, object] = {
        "claim_id": "c_000",
        "claim_text": "text",
        "span_start_seconds": 0.0,
        "span_end_seconds": 1.0,
        "verdict": "unverified",
        "sources": [],
        "annotation": None,
        "corrected_text": None,
    }
    raw_claim.update(overrides)
    return raw_claim


@pytest.mark.parametrize("verdict", ["confirmed", "disputed", "mixed"])
def test_verdict_with_empty_sources_is_rejected(verdict: str) -> None:
    payload = {
        "claims": [
            a_raw_claim(
                verdict=verdict,
                sources=[],
                annotation="note" if verdict in ("disputed", "mixed") else None,
            )
        ]
    }

    with pytest.raises(ClaimsPayloadError, match="sources"):
        parse_claims_payload(payload)


@pytest.mark.parametrize("verdict", ["disputed", "mixed"])
def test_annotated_verdict_with_null_annotation_is_rejected(verdict: str) -> None:
    payload = {
        "claims": [
            a_raw_claim(
                verdict=verdict,
                sources=["https://doi.org/10.1000/xyz"],
                annotation=None,
            )
        ]
    }

    with pytest.raises(ClaimsPayloadError, match="annotation"):
        parse_claims_payload(payload)


def test_payload_without_claim_id_derives_positional_ids() -> None:
    raw_first = a_raw_claim()
    raw_second = a_raw_claim()
    del raw_first["claim_id"]
    del raw_second["claim_id"]

    restored = parse_claims_payload({"claims": [raw_first, raw_second]})

    assert [claim.claim_id for claim in restored] == ["c_000", "c_001"]


def test_payload_without_corrected_text_parses_as_none() -> None:
    raw_claim = a_raw_claim()
    del raw_claim["corrected_text"]

    restored = parse_claims_payload({"claims": [raw_claim]})

    assert restored[0].corrected_text is None


def test_confirmed_with_annotation_is_rejected() -> None:
    payload = {
        "claims": [
            {
                "claim_text": "text",
                "span_start_seconds": 0.0,
                "span_end_seconds": 1.0,
                "verdict": "confirmed",
                "sources": ["https://doi.org/10.1000/xyz"],
                "annotation": "stray note",
            }
        ]
    }

    with pytest.raises(ClaimsPayloadError, match="annotation"):
        parse_claims_payload(payload)


def test_unknown_verdict_is_rejected() -> None:
    payload = {
        "claims": [
            {
                "claim_text": "text",
                "span_start_seconds": 0.0,
                "span_end_seconds": 1.0,
                "verdict": "plausible",
                "sources": [],
                "annotation": None,
            }
        ]
    }

    with pytest.raises(ClaimsPayloadError, match="verdict"):
        parse_claims_payload(payload)


def test_missing_field_is_rejected() -> None:
    payload = {
        "claims": [
            {
                "claim_text": "text",
                "span_start_seconds": 0.0,
                "verdict": "unverified",
                "sources": [],
                "annotation": None,
            }
        ]
    }

    with pytest.raises(ClaimsPayloadError, match="span_end_seconds"):
        parse_claims_payload(payload)


def test_missing_claims_key_is_rejected() -> None:
    with pytest.raises(ClaimsPayloadError, match="claims"):
        parse_claims_payload({})
