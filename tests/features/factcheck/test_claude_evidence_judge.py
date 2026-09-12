# @covers analysis:EXT-010
# @covers analysis:DLT-037
import json

import pytest

from konspekt.features.factcheck.adapters.outbound.claude_evidence_judge import (
    ClaudeEvidenceJudge,
)
from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    ClaudeRefusalError,
    FactcheckResponseError,
)
from konspekt.features.factcheck.domain.claims import Verdict
from konspekt.features.factcheck.domain.evidence import Evidence
from konspekt.features.factcheck.domain.evidenced_claim import EvidencedClaim
from konspekt.features.factcheck.domain.judged_claim import JudgedClaim
from tests.features.factcheck.claude_api_fakes import (
    FakeAnthropicClient,
    RecordingBudget,
    a_response,
)


def a_merge_sort_claim() -> EvidencedClaim:
    return EvidencedClaim(
        claim_text="Merge sort runs in O(n log n) time in the worst case",
        evidence=(
            Evidence(
                url="https://algs4.cs.princeton.edu/22mergesort/",
                title="Mergesort",
                published_date=None,
                excerpts=("Mergesort guarantees to sort an array of N items in time N log N.",),
            ),
        ),
    )


def a_judgement_text(results: list[dict[str, object]]) -> str:
    return json.dumps({"results": results})


def a_confirmed_result() -> dict[str, object]:
    return {"verdict": "confirmed", "evidence": [1], "annotation": None, "corrected_text": None}


def test_judge_request_sends_no_tools() -> None:
    client = FakeAnthropicClient(a_response(a_judgement_text([a_confirmed_result()])))
    judge = ClaudeEvidenceJudge(budget=RecordingBudget(), client=client)

    judge.judge_batch([a_merge_sort_claim()], "en")

    assert "tools" not in client.messages.calls[0]


def test_judge_request_uses_the_configured_model() -> None:
    client = FakeAnthropicClient(a_response(a_judgement_text([a_confirmed_result()])))
    judge = ClaudeEvidenceJudge(budget=RecordingBudget(), model="claude-opus-4-8", client=client)

    judge.judge_batch([a_merge_sort_claim()], "en")

    assert client.messages.calls[0]["model"] == "claude-opus-4-8"


def test_judge_prompt_carries_claim_and_numbered_evidence() -> None:
    client = FakeAnthropicClient(a_response(a_judgement_text([a_confirmed_result()])))
    judge = ClaudeEvidenceJudge(budget=RecordingBudget(), client=client)

    judge.judge_batch([a_merge_sort_claim()], "en")

    request_content = client.messages.calls[0]["messages"][0]["content"]
    assert isinstance(request_content, str)
    assert "Merge sort runs in O(n log n) time in the worst case" in request_content
    assert "Evidence 1" in request_content
    assert "https://algs4.cs.princeton.edu/22mergesort/" in request_content
    assert "time N log N" in request_content


def test_judge_returns_verdicts_with_cited_evidence_numbers() -> None:
    disputed = {
        "verdict": "disputed",
        "evidence": [1],
        "annotation": "The bound is n log n, not n squared.",
        "corrected_text": "Merge sort runs in O(n log n) time.",
    }
    client = FakeAnthropicClient(a_response(a_judgement_text([disputed])))
    judge = ClaudeEvidenceJudge(budget=RecordingBudget(), client=client)

    judged = judge.judge_batch([a_merge_sort_claim()], "en")

    assert judged == [
        JudgedClaim(
            verdict=Verdict.DISPUTED,
            cited_evidence_numbers=(1,),
            annotation="The bound is n log n, not n squared.",
            corrected_text="Merge sort runs in O(n log n) time.",
        )
    ]


def test_judge_charges_the_budget_from_reported_usage() -> None:
    client = FakeAnthropicClient(
        a_response(
            a_judgement_text([a_confirmed_result()]), input_tokens=4000, output_tokens=1000
        )
    )
    budget = RecordingBudget()
    judge = ClaudeEvidenceJudge(budget=budget, client=client)

    judge.judge_batch([a_merge_sort_claim()], "en")

    assert budget.charges == [pytest.approx(4000 * 5 / 1e6 + 1000 * 25 / 1e6)]


def test_judge_retries_a_schema_mismatch_once() -> None:
    client = FakeAnthropicClient(
        a_response('{"results": "not a list"}'),
        a_response(a_judgement_text([a_confirmed_result()])),
    )
    judge = ClaudeEvidenceJudge(budget=RecordingBudget(), client=client)

    judged = judge.judge_batch([a_merge_sort_claim()], "en")

    assert len(client.messages.calls) == 2
    assert judged[0].verdict is Verdict.CONFIRMED


def test_judge_schema_mismatch_twice_fails_after_two_requests() -> None:
    wrong_count = a_judgement_text([a_confirmed_result(), a_confirmed_result()])
    client = FakeAnthropicClient(a_response(wrong_count), a_response(wrong_count))
    judge = ClaudeEvidenceJudge(budget=RecordingBudget(), client=client)

    with pytest.raises(FactcheckResponseError, match="results"):
        judge.judge_batch([a_merge_sort_claim()], "en")

    assert len(client.messages.calls) == 2


def test_judge_refusal_raises_typed_error() -> None:
    client = FakeAnthropicClient(a_response("", stop_reason="refusal"))
    judge = ClaudeEvidenceJudge(budget=RecordingBudget(), client=client)

    with pytest.raises(ClaudeRefusalError, match="refused"):
        judge.judge_batch([a_merge_sort_claim()], "en")
