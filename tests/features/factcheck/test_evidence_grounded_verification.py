# @covers analysis:DLT-034
from collections.abc import Sequence

import pytest

from konspekt.features.factcheck.application.evidence_grounded_verification import (
    EvidenceGroundedVerification,
)
from konspekt.features.factcheck.domain.claims import Verdict, VerificationOutcome
from konspekt.features.factcheck.domain.evidence import Evidence
from konspekt.features.factcheck.domain.evidenced_claim import EvidencedClaim
from konspekt.features.factcheck.domain.judged_claim import JudgedClaim
from konspekt.features.factcheck.ports.outbound.search_credential_error import (
    SearchCredentialError,
)
from konspekt.features.factcheck.ports.outbound.search_credits_exhausted_error import (
    SearchCreditsExhaustedError,
)


class FakeSearch:
    def __init__(self, evidence_by_query: dict[str, list[Evidence]]) -> None:
        self._evidence_by_query = evidence_by_query
        self.queries: list[str] = []

    def search(self, query: str) -> list[Evidence]:
        self.queries.append(query)
        return self._evidence_by_query.get(query, [])


class FailingSearch:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def search(self, query: str) -> list[Evidence]:
        raise self._error


class FakeTranslation:
    def __init__(self, english_query_by_text: dict[str, str]) -> None:
        self._english_query_by_text = english_query_by_text
        self.requests: list[tuple[list[str], str]] = []

    def english_queries(self, claim_texts: Sequence[str], language: str) -> list[str]:
        self.requests.append((list(claim_texts), language))
        return [self._english_query_by_text.get(text, text) for text in claim_texts]


class FakeJudge:
    def __init__(self, judged_claim_by_text: dict[str, JudgedClaim]) -> None:
        self._judged_claim_by_text = judged_claim_by_text
        self.batches: list[tuple[list[EvidencedClaim], str]] = []

    def judge_batch(
        self, claims: Sequence[EvidencedClaim], language: str
    ) -> list[JudgedClaim]:
        self.batches.append((list(claims), language))
        return [self._judged_claim_by_text[claim.claim_text] for claim in claims]


def an_evidence(url: str, title: str = "Reference article") -> Evidence:
    return Evidence(
        url=url,
        title=title,
        published_date=None,
        excerpts=("An excerpt focused on the claim.",),
    )


@pytest.mark.parametrize(
    "search_error",
    [
        SearchCredentialError("Exa rejected the API key"),
        SearchCreditsExhaustedError("Exa credits exhausted"),
    ],
    ids=["credential", "credits"],
)
def test_search_error_propagates_unchanged(search_error: Exception) -> None:
    """# @covers analysis:REQ-022"""
    verification = EvidenceGroundedVerification(
        FailingSearch(search_error), FakeTranslation({}), FakeJudge({})
    )

    with pytest.raises(type(search_error)) as raised:
        verification.verify_batch(["Water boils at 100 C at sea level"], "en")

    assert raised.value is search_error


def test_english_batch_searches_each_claim_once_by_its_text() -> None:
    """# @covers analysis:REQ-022"""
    search = FakeSearch({})
    verification = EvidenceGroundedVerification(search, FakeTranslation({}), FakeJudge({}))

    verification.verify_batch(
        ["Water boils at 100 C at sea level", "The Sun is a planet"], "en"
    )

    assert sorted(search.queries) == sorted(
        ["Water boils at 100 C at sea level", "The Sun is a planet"]
    )


@pytest.mark.parametrize(
    ("judged_claim", "expected_outcome"),
    [
        (
            JudgedClaim(
                verdict=Verdict.DISPUTED,
                cited_evidence_numbers=(1,),
                annotation="The measured value is 299,792 km/s.",
                corrected_text="Light travels at 299,792 km/s.",
            ),
            VerificationOutcome(
                verdict=Verdict.DISPUTED,
                sources=("https://en.wikipedia.org/wiki/Speed_of_light",),
                annotation="The measured value is 299,792 km/s.",
                corrected_text="Light travels at 299,792 km/s.",
                evidence_urls=("https://en.wikipedia.org/wiki/Speed_of_light",),
            ),
        ),
        (
            JudgedClaim(
                verdict=Verdict.CONFIRMED,
                cited_evidence_numbers=(1,),
                annotation=None,
                corrected_text=None,
            ),
            VerificationOutcome(
                verdict=Verdict.CONFIRMED,
                sources=("https://en.wikipedia.org/wiki/Speed_of_light",),
                annotation=None,
                corrected_text=None,
                evidence_urls=("https://en.wikipedia.org/wiki/Speed_of_light",),
            ),
        ),
    ],
    ids=["disputed", "confirmed"],
)
def test_judged_claim_is_stored_with_its_cited_evidence_url(
    judged_claim: JudgedClaim, expected_outcome: VerificationOutcome
) -> None:
    """# @covers analysis:REQ-022"""
    claim_text = "Light travels at 300,000 km/s"
    search = FakeSearch(
        {claim_text: [an_evidence("https://en.wikipedia.org/wiki/Speed_of_light")]}
    )
    judge = FakeJudge({claim_text: judged_claim})
    verification = EvidenceGroundedVerification(search, FakeTranslation({}), judge)

    outcomes = verification.verify_batch([claim_text], "en")

    assert outcomes == [expected_outcome]


def test_sources_are_cited_evidence_urls_in_citation_order() -> None:
    """# @covers analysis:REQ-022"""
    claim_text = "Light travels at 300,000 km/s"
    search = FakeSearch(
        {
            claim_text: [
                an_evidence("https://en.wikipedia.org/wiki/Speed_of_light"),
                an_evidence("https://www.britannica.com/science/speed-of-light"),
                an_evidence("https://physics.nist.gov/cgi-bin/cuu/Value?c"),
            ]
        }
    )
    judge = FakeJudge(
        {
            claim_text: JudgedClaim(
                verdict=Verdict.DISPUTED,
                cited_evidence_numbers=(3, 1),
                annotation="The measured value is 299,792 km/s.",
                corrected_text=None,
            )
        }
    )
    verification = EvidenceGroundedVerification(search, FakeTranslation({}), judge)

    outcomes = verification.verify_batch([claim_text], "en")

    assert outcomes[0].sources == (
        "https://physics.nist.gov/cgi-bin/cuu/Value?c",
        "https://en.wikipedia.org/wiki/Speed_of_light",
    )


def test_evidence_urls_list_every_evidence_url_of_the_claim() -> None:
    """# @covers analysis:REQ-022"""
    claim_text = "Light travels at 300,000 km/s"
    search = FakeSearch(
        {
            claim_text: [
                an_evidence("https://en.wikipedia.org/wiki/Speed_of_light"),
                an_evidence("https://www.britannica.com/science/speed-of-light"),
            ]
        }
    )
    judge = FakeJudge(
        {
            claim_text: JudgedClaim(
                verdict=Verdict.CONFIRMED,
                cited_evidence_numbers=(2,),
                annotation=None,
                corrected_text=None,
            )
        }
    )
    verification = EvidenceGroundedVerification(search, FakeTranslation({}), judge)

    outcomes = verification.verify_batch([claim_text], "en")

    assert outcomes[0].evidence_urls == (
        "https://en.wikipedia.org/wiki/Speed_of_light",
        "https://www.britannica.com/science/speed-of-light",
    )


@pytest.mark.parametrize(
    "cited_evidence_numbers",
    [(0,), (3,), (-1,), (1, 3)],
    ids=["zero", "past_last", "negative", "one_of_two_outside"],
)
def test_citation_outside_the_claim_evidence_is_unverified(
    cited_evidence_numbers: tuple[int, ...],
) -> None:
    """# @covers analysis:REQ-022"""
    claim_text = "Light travels at 300,000 km/s"
    search = FakeSearch(
        {
            claim_text: [
                an_evidence("https://en.wikipedia.org/wiki/Speed_of_light"),
                an_evidence("https://www.britannica.com/science/speed-of-light"),
            ]
        }
    )
    judge = FakeJudge(
        {
            claim_text: JudgedClaim(
                verdict=Verdict.DISPUTED,
                cited_evidence_numbers=cited_evidence_numbers,
                annotation="The measured value is 299,792 km/s.",
                corrected_text="Light travels at 299,792 km/s.",
            )
        }
    )
    verification = EvidenceGroundedVerification(search, FakeTranslation({}), judge)

    outcomes = verification.verify_batch([claim_text], "en")

    assert outcomes == [
        VerificationOutcome(
            verdict=Verdict.UNVERIFIED,
            sources=(),
            annotation=None,
            corrected_text=None,
            evidence_urls=(
                "https://en.wikipedia.org/wiki/Speed_of_light",
                "https://www.britannica.com/science/speed-of-light",
            ),
        )
    ]


def test_claim_without_evidence_is_unverified() -> None:
    """# @covers analysis:REQ-022"""
    verification = EvidenceGroundedVerification(
        FakeSearch({}), FakeTranslation({}), FakeJudge({})
    )

    outcomes = verification.verify_batch(["The Sun is a planet"], "en")

    assert outcomes == [
        VerificationOutcome(
            verdict=Verdict.UNVERIFIED,
            sources=(),
            annotation=None,
            corrected_text=None,
            evidence_urls=(),
        )
    ]


def test_batch_without_any_evidence_makes_no_judge_request() -> None:
    """# @covers analysis:REQ-022"""
    judge = FakeJudge({})
    verification = EvidenceGroundedVerification(FakeSearch({}), FakeTranslation({}), judge)

    verification.verify_batch(["The Sun is a planet"], "en")

    assert judge.batches == []


def test_outcomes_follow_claim_order_when_a_claim_lacks_evidence() -> None:
    """# @covers analysis:REQ-022"""
    search = FakeSearch(
        {
            "Water boils at 100 C at sea level": [
                an_evidence("https://en.wikipedia.org/wiki/Boiling_point")
            ],
            "Light travels at 300,000 km/s": [
                an_evidence("https://en.wikipedia.org/wiki/Speed_of_light")
            ],
        }
    )
    judge = FakeJudge(
        {
            "Water boils at 100 C at sea level": JudgedClaim(
                verdict=Verdict.CONFIRMED,
                cited_evidence_numbers=(1,),
                annotation=None,
                corrected_text=None,
            ),
            "Light travels at 300,000 km/s": JudgedClaim(
                verdict=Verdict.DISPUTED,
                cited_evidence_numbers=(1,),
                annotation="The measured value is 299,792 km/s.",
                corrected_text=None,
            ),
        }
    )
    verification = EvidenceGroundedVerification(search, FakeTranslation({}), judge)

    outcomes = verification.verify_batch(
        [
            "Water boils at 100 C at sea level",
            "The Sun is a planet",
            "Light travels at 300,000 km/s",
        ],
        "en",
    )

    assert [outcome.verdict for outcome in outcomes] == [
        Verdict.CONFIRMED,
        Verdict.UNVERIFIED,
        Verdict.DISPUTED,
    ]


def test_non_english_batch_requests_english_queries_once() -> None:
    """# @covers analysis:REQ-022"""
    translation = FakeTranslation(
        {
            "Скорость света составляет 300 000 км/с": "speed of light is 300,000 km/s",
            "Вода кипит при 100 градусах": "water boils at 100 degrees",
        }
    )
    verification = EvidenceGroundedVerification(FakeSearch({}), translation, FakeJudge({}))

    verification.verify_batch(
        ["Скорость света составляет 300 000 км/с", "Вода кипит при 100 градусах"], "ru"
    )

    assert translation.requests == [
        (["Скорость света составляет 300 000 км/с", "Вода кипит при 100 градусах"], "ru")
    ]


def test_non_english_batch_searches_each_claim_in_both_languages() -> None:
    """# @covers analysis:REQ-022"""
    search = FakeSearch({})
    translation = FakeTranslation(
        {
            "Скорость света составляет 300 000 км/с": "speed of light is 300,000 km/s",
            "Вода кипит при 100 градусах": "water boils at 100 degrees",
        }
    )
    verification = EvidenceGroundedVerification(search, translation, FakeJudge({}))

    verification.verify_batch(
        ["Скорость света составляет 300 000 км/с", "Вода кипит при 100 градусах"], "ru"
    )

    assert sorted(search.queries) == sorted(
        [
            "Скорость света составляет 300 000 км/с",
            "speed of light is 300,000 km/s",
            "Вода кипит при 100 градусах",
            "water boils at 100 degrees",
        ]
    )


def test_english_batch_makes_no_translation_request() -> None:
    """# @covers analysis:REQ-022"""
    translation = FakeTranslation({})
    verification = EvidenceGroundedVerification(FakeSearch({}), translation, FakeJudge({}))

    verification.verify_batch(["Water boils at 100 C at sea level"], "en")

    assert translation.requests == []


def test_lecture_language_evidence_precedes_english_evidence() -> None:
    """# @covers analysis:REQ-022"""
    claim_text = "Скорость света составляет 300 000 км/с"
    lecture_evidence = an_evidence("https://ru.wikipedia.org/wiki/Скорость_света")
    english_evidence = an_evidence("https://en.wikipedia.org/wiki/Speed_of_light")
    search = FakeSearch(
        {
            claim_text: [lecture_evidence],
            "speed of light is 300,000 km/s": [english_evidence],
        }
    )
    translation = FakeTranslation({claim_text: "speed of light is 300,000 km/s"})
    judge = FakeJudge(
        {
            claim_text: JudgedClaim(
                verdict=Verdict.DISPUTED,
                cited_evidence_numbers=(2,),
                annotation="Точное значение 299 792 км/с.",
                corrected_text=None,
            )
        }
    )
    verification = EvidenceGroundedVerification(search, translation, judge)

    verification.verify_batch([claim_text], "ru")

    assert judge.batches == [
        (
            [EvidencedClaim(claim_text=claim_text, evidence=(lecture_evidence, english_evidence))],
            "ru",
        )
    ]


def test_evidence_found_by_both_queries_is_kept_once_as_first_found() -> None:
    """# @covers analysis:REQ-022"""
    claim_text = "Скорость света составляет 300 000 км/с"
    lecture_evidence = an_evidence(
        "https://en.wikipedia.org/wiki/Speed_of_light", title="Скорость света"
    )
    repeated_english_evidence = an_evidence(
        "https://en.wikipedia.org/wiki/Speed_of_light", title="Speed of light"
    )
    english_only_evidence = an_evidence("https://www.britannica.com/science/speed-of-light")
    search = FakeSearch(
        {
            claim_text: [lecture_evidence],
            "speed of light is 300,000 km/s": [repeated_english_evidence, english_only_evidence],
        }
    )
    translation = FakeTranslation({claim_text: "speed of light is 300,000 km/s"})
    judge = FakeJudge(
        {
            claim_text: JudgedClaim(
                verdict=Verdict.DISPUTED,
                cited_evidence_numbers=(1,),
                annotation="Точное значение 299 792 км/с.",
                corrected_text=None,
            )
        }
    )
    verification = EvidenceGroundedVerification(search, translation, judge)

    verification.verify_batch([claim_text], "ru")

    assert judge.batches == [
        (
            [
                EvidencedClaim(
                    claim_text=claim_text, evidence=(lecture_evidence, english_only_evidence)
                )
            ],
            "ru",
        )
    ]
