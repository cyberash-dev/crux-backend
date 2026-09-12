import json
from collections.abc import Mapping, Sequence

from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    FactcheckResponseError,
)
from konspekt.features.factcheck.domain.claims import Verdict
from konspekt.features.factcheck.domain.evidence import Evidence
from konspekt.features.factcheck.domain.evidenced_claim import EvidencedClaim
from konspekt.features.factcheck.domain.judged_claim import JudgedClaim

EVIDENCE_JUDGE_INSTRUCTIONS = (
    "You are a fact-checker. You receive numbered lecture claims, each followed by "
    "numbered evidence excerpts retrieved from the web for that claim. Grade every "
    "claim using ONLY its own evidence. "
    '"confirmed": the evidence supports the claim. "disputed": the evidence '
    'contradicts it. "mixed": the claim is correct or incorrect depending on scope, '
    'terminology or pedagogical simplification. "unverified": the evidence does not '
    "settle the claim. For confirmed, disputed and mixed cite the numbers of the "
    "supporting evidence of that claim, most authoritative first: peer-reviewed "
    "articles, textbooks, university course material and encyclopedias rank above "
    "blogs, forums and commercial sites. "
    "Respond with exactly one JSON object and nothing else: "
    '{"results": [{"verdict": "confirmed" | "disputed" | "mixed" | "unverified", '
    '"evidence": [evidence numbers of this claim], '
    '"annotation": one sentence describing the disagreement for a disputed or mixed '
    'verdict, otherwise null, "corrected_text": the precise corrected wording of a '
    "disputed claim, otherwise null}, ...]}. "
    "results MUST contain exactly one entry per claim, in the input order. "
    "Write annotations and corrected wording in the language of the lecture."
)


def evidence_judge_prompt(claims: Sequence[EvidencedClaim], language: str) -> str:
    claim_blocks = "\n\n".join(
        _claim_block(claim_number, claim)
        for claim_number, claim in enumerate(claims, start=1)
    )
    return (
        f"{EVIDENCE_JUDGE_INSTRUCTIONS}\n"
        f"Lecture language: {language}\n\n"
        f"{claim_blocks}"
    )


def parse_judged_claims(final_text: str, expected_count: int) -> list[JudgedClaim]:
    results = json_object(final_text).get("results")
    if not isinstance(results, list) or len(results) != expected_count:
        raise FactcheckResponseError(
            f"results must be a list of {expected_count} entries"
        )
    return [_judged_claim(entry) for entry in results]


def json_object(final_text: str) -> Mapping[str, object]:
    start, end = final_text.find("{"), final_text.rfind("}")
    if start == -1 or end < start:
        raise FactcheckResponseError("response carries no JSON object")
    try:
        payload = json.loads(final_text[start : end + 1])
    except json.JSONDecodeError as error:
        raise FactcheckResponseError(f"response JSON is malformed: {error}") from error
    if not isinstance(payload, dict):
        raise FactcheckResponseError("response JSON is not an object")
    return payload


def _claim_block(claim_number: int, claim: EvidencedClaim) -> str:
    evidence_lines = "\n".join(
        _evidence_block(evidence_number, evidence)
        for evidence_number, evidence in enumerate(claim.evidence, start=1)
    )
    return f"Claim {claim_number}: {claim.claim_text}\n{evidence_lines}"


def _evidence_block(evidence_number: int, evidence: Evidence) -> str:
    published = f" (published {evidence.published_date})" if evidence.published_date else ""
    excerpts = "\n    ".join(evidence.excerpts)
    return f"  Evidence {evidence_number}: {evidence.title} | {evidence.url}{published}\n    {excerpts}"


def _judged_claim(entry: object) -> JudgedClaim:
    if not isinstance(entry, dict):
        raise FactcheckResponseError("each result must be an object")
    return JudgedClaim(
        verdict=_verdict(entry.get("verdict")),
        cited_evidence_numbers=_cited_numbers(entry.get("evidence")),
        annotation=_optional_text(entry.get("annotation"), "annotation"),
        corrected_text=_optional_text(entry.get("corrected_text"), "corrected_text"),
    )


def _verdict(raw_verdict: object) -> Verdict:
    try:
        return Verdict(raw_verdict)
    except ValueError as error:
        raise FactcheckResponseError(f"unknown verdict: {raw_verdict!r}") from error


def _cited_numbers(raw_numbers: object) -> tuple[int, ...]:
    if not isinstance(raw_numbers, list) or not all(
        isinstance(number, int) and not isinstance(number, bool) for number in raw_numbers
    ):
        raise FactcheckResponseError("evidence must be a list of integers")
    return tuple(raw_numbers)


def _optional_text(raw_text: object, field_name: str) -> str | None:
    if raw_text is not None and not isinstance(raw_text, str):
        raise FactcheckResponseError(f"{field_name} must be a string or null")
    return raw_text
