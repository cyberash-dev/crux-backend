# @covers analysis:CON-021
# @covers analysis:REQ-022
# @covers analysis:DLT-032
import time
from collections.abc import Sequence

import pytest

from konspekt.features.factcheck.application.check_claims import BATCH_SIZE, check_claims
from konspekt.features.factcheck.domain.claims import (
    ExtractedClaim,
    Verdict,
    VerificationOutcome,
)
from konspekt.features.factcheck.ports.outbound.search_credential_error import (
    SearchCredentialError,
)
from konspekt.features.factcheck.ports.outbound.search_credits_exhausted_error import (
    SearchCreditsExhaustedError,
)
from konspekt.shared.budget import BudgetExceededError
from konspekt.shared.timecode import TimeRange


class FakeExtraction:
    def __init__(self, claims: list[ExtractedClaim]) -> None:
        self._claims = claims

    def extract_claims(
        self, core_text_with_timestamps: str, language: str
    ) -> list[ExtractedClaim]:
        return self._claims


class FakeVerification:
    def __init__(self, outcomes_by_claim_text: dict[str, VerificationOutcome]) -> None:
        self._outcomes_by_claim_text = outcomes_by_claim_text
        self.batches: list[list[str]] = []

    def verify_batch(
        self, claim_texts: Sequence[str], language: str
    ) -> list[VerificationOutcome]:
        self.batches.append(list(claim_texts))
        return [self._outcomes_by_claim_text[text] for text in claim_texts]


class FailingBatchVerification:
    def __init__(self, failing_claim_text: str, outcome: VerificationOutcome) -> None:
        self._failing_claim_text = failing_claim_text
        self._outcome = outcome

    def verify_batch(
        self, claim_texts: Sequence[str], language: str
    ) -> list[VerificationOutcome]:
        if self._failing_claim_text in claim_texts:
            raise ConnectionError("verification backend unavailable")
        return [self._outcome for _ in claim_texts]


class WrongLengthVerification:
    def verify_batch(
        self, claim_texts: Sequence[str], language: str
    ) -> list[VerificationOutcome]:
        return [
            VerificationOutcome(
                verdict=Verdict.CONFIRMED,
                sources=("https://doi.org/10.1000/ok",),
                evidence_urls=("https://doi.org/10.1000/ok",),
                annotation=None,
            )
        ] * (len(claim_texts) + 1)


def a_claim(text: str, start_seconds: float = 0.0) -> ExtractedClaim:
    return ExtractedClaim(
        claim_text=text, span=TimeRange(start_seconds, start_seconds + 10.0)
    )


def a_confirmed_outcome() -> VerificationOutcome:
    return VerificationOutcome(
        verdict=Verdict.CONFIRMED,
        sources=("https://doi.org/10.1000/ok",),
        evidence_urls=("https://doi.org/10.1000/ok",),
        annotation=None,
    )


def seven_claim_texts() -> list[str]:
    return [f"claim {index}" for index in range(BATCH_SIZE + 2)]


def test_every_extracted_claim_is_verified_and_gated() -> None:
    claims = [a_claim("DNA has two strands"), a_claim("The Sun is a planet", 20.0)]
    extraction = FakeExtraction(claims)
    verification = FakeVerification(
        {
            "DNA has two strands": VerificationOutcome(
                verdict=Verdict.CONFIRMED,
                sources=("https://pubmed.ncbi.nlm.nih.gov/1",),
                evidence_urls=("https://pubmed.ncbi.nlm.nih.gov/1",),
                annotation=None,
            ),
            "The Sun is a planet": VerificationOutcome(
                verdict=Verdict.DISPUTED,
                sources=("https://doi.org/10.1000/astro",),
                evidence_urls=("https://doi.org/10.1000/astro",),
                annotation="The Sun is a star, not a planet.",
            ),
        }
    )

    checked = check_claims(
        "core text", "en", extraction, verification
    )

    assert [claim.claim_text for claim in checked] == [
        "DNA has two strands",
        "The Sun is a planet",
    ]
    assert [claim.verdict for claim in checked] == [Verdict.CONFIRMED, Verdict.DISPUTED]
    assert checked[1].annotation == "The Sun is a star, not a planet."


def test_seven_claims_are_verified_in_two_batches_of_five_and_two() -> None:
    claim_texts = seven_claim_texts()
    extraction = FakeExtraction(
        [a_claim(text, index * 20.0) for index, text in enumerate(claim_texts)]
    )
    verification = FakeVerification(
        {text: a_confirmed_outcome() for text in claim_texts}
    )

    checked = check_claims(
        "core text", "en", extraction, verification
    )

    assert sorted(verification.batches) == sorted(
        [claim_texts[:BATCH_SIZE], claim_texts[BATCH_SIZE:]]
    )
    assert [claim.claim_text for claim in checked] == claim_texts


def test_failed_batch_is_unverified_while_other_batches_continue() -> None:
    claim_texts = seven_claim_texts()
    extraction = FakeExtraction(
        [a_claim(text, index * 20.0) for index, text in enumerate(claim_texts)]
    )
    verification = FailingBatchVerification(
        failing_claim_text="claim 0", outcome=a_confirmed_outcome()
    )

    checked = check_claims(
        "core text", "en", extraction, verification
    )

    assert [claim.claim_text for claim in checked] == claim_texts
    assert [claim.verdict for claim in checked[:BATCH_SIZE]] == (
        [Verdict.UNVERIFIED] * BATCH_SIZE
    )
    assert checked[0].sources == ()
    assert checked[0].annotation is None
    assert [claim.verdict for claim in checked[BATCH_SIZE:]] == [Verdict.CONFIRMED] * 2


def test_batch_with_mismatched_response_length_is_unverified() -> None:
    claims = [a_claim("first"), a_claim("second", 20.0)]
    extraction = FakeExtraction(claims)

    checked = check_claims(
        "core text", "en", extraction, WrongLengthVerification()
    )

    assert [claim.verdict for claim in checked] == [Verdict.UNVERIFIED] * 2
    assert [claim.claim_text for claim in checked] == ["first", "second"]


def test_budget_exceeded_during_verification_aborts_the_stage() -> None:
    # @covers pipeline:POL-002
    claims = [a_claim("first"), a_claim("second", 20.0)]
    extraction = FakeExtraction(claims)

    class BudgetExhaustedVerification:
        def verify_batch(
            self, claim_texts: Sequence[str], language: str
        ) -> list[VerificationOutcome]:
            raise BudgetExceededError(spent_usd=9.9, max_usd=10.0, attempted_usd=0.5)

    with pytest.raises(BudgetExceededError):
        check_claims(
            "core text", "en", extraction, BudgetExhaustedVerification()
        )


class RaisingVerification:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def verify_batch(
        self, claim_texts: Sequence[str], language: str
    ) -> list[VerificationOutcome]:
        raise self._error


@pytest.mark.parametrize(
    "search_error",
    [
        SearchCredentialError("Exa rejected the API key (HTTP 401)"),
        SearchCreditsExhaustedError("Exa credits exhausted (HTTP 402)"),
    ],
    ids=["rejected key", "credits exhausted"],
)
def test_search_account_failure_aborts_the_stage(search_error: Exception) -> None:
    # @covers analysis:EXT-014
    extraction = FakeExtraction([a_claim("first"), a_claim("second", 20.0)])

    with pytest.raises(type(search_error), match="HTTP 40"):
        check_claims("core text", "en", extraction, RaisingVerification(search_error))


def test_no_extracted_claims_yields_empty_result() -> None:
    extraction = FakeExtraction([])
    verification = FakeVerification({})

    checked = check_claims(
        "core text", "en", extraction, verification
    )

    assert checked == []


def test_claim_ids_are_assigned_by_position() -> None:
    claim_texts = seven_claim_texts()
    extraction = FakeExtraction(
        [a_claim(text, index * 20.0) for index, text in enumerate(claim_texts)]
    )
    verification = FakeVerification({text: a_confirmed_outcome() for text in claim_texts})

    checked = check_claims(
        "core text", "en", extraction, verification
    )

    assert [claim.claim_id for claim in checked] == [
        "c_000", "c_001", "c_002", "c_003", "c_004", "c_005", "c_006",
    ]


def test_duplicate_sources_are_deduplicated_preserving_order() -> None:
    extraction = FakeExtraction([a_claim("DNA has two strands")])
    verification = FakeVerification(
        {
            "DNA has two strands": VerificationOutcome(
                verdict=Verdict.CONFIRMED,
                sources=(
                    "https://doi.org/10.1000/first",
                    "https://doi.org/10.1000/second",
                    "https://doi.org/10.1000/first",
                ),
                evidence_urls=(
                    "https://doi.org/10.1000/first",
                    "https://doi.org/10.1000/second",
                ),
                annotation=None,
            )
        }
    )

    checked = check_claims(
        "core text", "en", extraction, verification
    )

    assert checked[0].sources == (
        "https://doi.org/10.1000/first",
        "https://doi.org/10.1000/second",
    )


def test_parallel_verification_preserves_claim_order() -> None:
    claim_texts = seven_claim_texts()

    class SlowFirstBatchVerification:
        def verify_batch(
            self, claim_texts_in_batch: Sequence[str], language: str
        ) -> list[VerificationOutcome]:
            if "claim 0" in claim_texts_in_batch:
                time.sleep(0.05)
            return [
                VerificationOutcome(
                    verdict=Verdict.CONFIRMED,
                    sources=(f"https://example.org/{text}",),
                    evidence_urls=(f"https://example.org/{text}",),
                    annotation=None,
                )
                for text in claim_texts_in_batch
            ]

    extraction = FakeExtraction(
        [a_claim(text, index * 20.0) for index, text in enumerate(claim_texts)]
    )

    checked = check_claims(
        "текст",
        "ru",
        extraction,
        SlowFirstBatchVerification(),
        max_workers=3,
    )

    assert [claim.claim_text for claim in checked] == claim_texts
    assert [claim.sources for claim in checked] == [
        (f"https://example.org/{text}",) for text in claim_texts
    ]
