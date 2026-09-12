# @covers analysis:EXT-011
# @covers analysis:DLT-036
import json

import pytest

from konspekt.features.factcheck.adapters.outbound.claude_cli_evidence_judge import (
    ClaudeCliEvidenceJudge,
)
from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    FactcheckResponseError,
)
from konspekt.features.factcheck.domain.claims import Verdict
from konspekt.features.factcheck.domain.evidence import Evidence
from konspekt.features.factcheck.domain.evidenced_claim import EvidencedClaim
from konspekt.features.factcheck.domain.judged_claim import JudgedClaim
from konspekt.shared.claude_cli import ClaudeCliResult
from tests.features.factcheck.claude_cli_fakes import FakeRunner, RecordingBudget


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


def a_judgement(results: list[dict[str, object]], cost_usd: float = 0.05) -> ClaudeCliResult:
    return ClaudeCliResult(text=json.dumps({"results": results}), cost_usd=cost_usd)


def a_confirmed_result() -> dict[str, object]:
    return {"verdict": "confirmed", "evidence": [1], "annotation": None, "corrected_text": None}


def test_judge_runs_without_tools_on_the_configured_model() -> None:
    runner = FakeRunner(a_judgement([a_confirmed_result()]))
    judge = ClaudeCliEvidenceJudge(budget=RecordingBudget(), model="claude-opus-5", runner=runner)

    judge.judge_batch([a_merge_sort_claim()], "en")

    assert runner.calls[0]["allowed_tools"] == ()
    assert runner.calls[0]["model"] == "claude-opus-5"


def test_judge_prompt_carries_claim_and_numbered_evidence() -> None:
    runner = FakeRunner(a_judgement([a_confirmed_result()]))
    judge = ClaudeCliEvidenceJudge(budget=RecordingBudget(), runner=runner)

    judge.judge_batch([a_merge_sort_claim()], "en")

    prompt = str(runner.calls[0]["prompt"])
    assert "Merge sort runs in O(n log n) time in the worst case" in prompt
    assert "Evidence 1" in prompt
    assert "https://algs4.cs.princeton.edu/22mergesort/" in prompt
    assert "time N log N" in prompt


def test_judge_returns_verdicts_with_cited_evidence_numbers() -> None:
    disputed = {
        "verdict": "disputed",
        "evidence": [1],
        "annotation": "The bound is n log n, not n squared.",
        "corrected_text": "Merge sort runs in O(n log n) time.",
    }
    judge = ClaudeCliEvidenceJudge(budget=RecordingBudget(), runner=FakeRunner(a_judgement([disputed])))

    judged = judge.judge_batch([a_merge_sort_claim()], "en")

    assert judged == [
        JudgedClaim(
            verdict=Verdict.DISPUTED,
            cited_evidence_numbers=(1,),
            annotation="The bound is n log n, not n squared.",
            corrected_text="Merge sort runs in O(n log n) time.",
        )
    ]


def test_judge_charges_the_budget_with_the_run_cost() -> None:
    budget = RecordingBudget()
    judge = ClaudeCliEvidenceJudge(
        budget=budget, runner=FakeRunner(a_judgement([a_confirmed_result()], cost_usd=0.07))
    )

    judge.judge_batch([a_merge_sort_claim()], "en")

    assert budget.charges == [0.07]


def test_judge_retries_a_schema_mismatch_once() -> None:
    malformed = ClaudeCliResult(text='{"results": "not a list"}', cost_usd=0.01)
    runner = FakeRunner(malformed, a_judgement([a_confirmed_result()]))
    judge = ClaudeCliEvidenceJudge(budget=RecordingBudget(), runner=runner)

    judged = judge.judge_batch([a_merge_sort_claim()], "en")

    assert len(runner.calls) == 2
    assert judged[0].verdict is Verdict.CONFIRMED


def test_judge_fails_after_a_second_schema_mismatch() -> None:
    wrong_count = a_judgement([a_confirmed_result(), a_confirmed_result()])
    judge = ClaudeCliEvidenceJudge(
        budget=RecordingBudget(), runner=FakeRunner(wrong_count, wrong_count)
    )

    with pytest.raises(FactcheckResponseError, match="results"):
        judge.judge_batch([a_merge_sort_claim()], "en")


@pytest.mark.parametrize(
    "citation",
    [["1"], [True], "1"],
    ids=["string number", "boolean", "not a list"],
)
def test_judge_rejects_citations_that_are_not_integer_lists(citation: object) -> None:
    malformed = a_judgement([{**a_confirmed_result(), "evidence": citation}])
    judge = ClaudeCliEvidenceJudge(budget=RecordingBudget(), runner=FakeRunner(malformed, malformed))

    with pytest.raises(FactcheckResponseError, match="evidence"):
        judge.judge_batch([a_merge_sort_claim()], "en")
