from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor

from konspekt.features.factcheck.domain.claims import Verdict, VerificationOutcome
from konspekt.features.factcheck.domain.evidence import Evidence
from konspekt.features.factcheck.domain.evidenced_claim import EvidencedClaim
from konspekt.features.factcheck.domain.judged_claim import JudgedClaim
from konspekt.features.factcheck.ports.outbound.claim_translation import ClaimTranslationPort
from konspekt.features.factcheck.ports.outbound.evidence_judge import EvidenceJudgePort
from konspekt.features.factcheck.ports.outbound.evidence_search import EvidenceSearchPort

_UNVERIFIED_OUTCOME = VerificationOutcome(verdict=Verdict.UNVERIFIED, sources=(), annotation=None)


class EvidenceGroundedVerification:
    def __init__(
        self,
        search: EvidenceSearchPort,
        translation: ClaimTranslationPort,
        judge: EvidenceJudgePort,
        max_search_workers: int = 5,
    ) -> None:
        self._search = search
        self._translation = translation
        self._judge = judge
        self._max_search_workers = max_search_workers

    def verify_batch(
        self, claim_texts: Sequence[str], language: str
    ) -> list[VerificationOutcome]:
        evidenced_claims = [
            EvidencedClaim(claim_text=claim_text, evidence=evidence)
            for claim_text, evidence in zip(
                claim_texts, self._evidence_per_claim(claim_texts, language), strict=True
            )
        ]
        claims_with_evidence = [claim for claim in evidenced_claims if claim.evidence]
        judged_outcome_queue = iter(self._judged_outcomes(claims_with_evidence, language))
        return [
            next(judged_outcome_queue) if claim.evidence else _UNVERIFIED_OUTCOME
            for claim in evidenced_claims
        ]

    def _evidence_per_claim(
        self, claim_texts: Sequence[str], language: str
    ) -> list[tuple[Evidence, ...]]:
        queries_per_claim = self._queries_per_claim(claim_texts, language)
        with ThreadPoolExecutor(max_workers=self._max_search_workers) as pool:
            search_futures_per_claim = [
                [pool.submit(self._search.search, query) for query in queries]
                for queries in queries_per_claim
            ]
            return [
                _deduplicated_by_url(
                    evidence
                    for search_future in search_futures
                    for evidence in search_future.result()
                )
                for search_futures in search_futures_per_claim
            ]

    def _queries_per_claim(
        self, claim_texts: Sequence[str], language: str
    ) -> list[tuple[str, ...]]:
        if language == "en":
            return [(claim_text,) for claim_text in claim_texts]
        english_queries = self._translation.english_queries(claim_texts, language)
        return [
            (claim_text, english_query)
            for claim_text, english_query in zip(claim_texts, english_queries, strict=True)
        ]

    def _judged_outcomes(
        self, claims_with_evidence: Sequence[EvidencedClaim], language: str
    ) -> list[VerificationOutcome]:
        if not claims_with_evidence:
            return []
        judged_claims = self._judge.judge_batch(claims_with_evidence, language)
        return [
            _judged_outcome(claim, judged)
            for claim, judged in zip(claims_with_evidence, judged_claims, strict=True)
        ]


def _deduplicated_by_url(found_evidence: Iterable[Evidence]) -> tuple[Evidence, ...]:
    evidence_by_url: dict[str, Evidence] = {}
    for evidence in found_evidence:
        evidence_by_url.setdefault(evidence.url, evidence)
    return tuple(evidence_by_url.values())


def _judged_outcome(claim: EvidencedClaim, judged: JudgedClaim) -> VerificationOutcome:
    evidence_urls = tuple(evidence.url for evidence in claim.evidence)
    is_every_citation_in_evidence = all(
        1 <= number <= len(evidence_urls) for number in judged.cited_evidence_numbers
    )
    if not is_every_citation_in_evidence:
        return VerificationOutcome(
            verdict=Verdict.UNVERIFIED,
            sources=(),
            annotation=None,
            corrected_text=None,
            evidence_urls=evidence_urls,
        )
    return VerificationOutcome(
        verdict=judged.verdict,
        sources=tuple(evidence_urls[number - 1] for number in judged.cited_evidence_numbers),
        annotation=judged.annotation,
        corrected_text=judged.corrected_text,
        evidence_urls=evidence_urls,
    )
