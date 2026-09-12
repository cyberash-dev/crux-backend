# @covers analysis:EXT-011
# @covers analysis:DLT-036
import json

import pytest

from konspekt.features.factcheck.adapters.outbound.claude_cli_claim_translation import (
    ClaudeCliClaimTranslation,
)
from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    FactcheckResponseError,
)
from konspekt.shared.claude_cli import ClaudeCliResult
from tests.features.factcheck.claude_cli_fakes import FakeRunner, RecordingBudget

RUSSIAN_CLAIMS = ["Сортировка слиянием работает за O(n log n)", "Число Пи иррационально"]


def a_translation(queries: list[str], cost_usd: float = 0.01) -> ClaudeCliResult:
    return ClaudeCliResult(text=json.dumps({"queries": queries}), cost_usd=cost_usd)


def english_queries() -> list[str]:
    return ["merge sort runs in O(n log n)", "pi is irrational"]


def test_translation_returns_one_english_query_per_claim() -> None:
    translation = ClaudeCliClaimTranslation(
        budget=RecordingBudget(), runner=FakeRunner(a_translation(english_queries()))
    )

    queries = translation.english_queries(RUSSIAN_CLAIMS, "ru")

    assert queries == english_queries()


def test_translation_runs_without_tools_and_sends_every_claim() -> None:
    runner = FakeRunner(a_translation(english_queries()))
    translation = ClaudeCliClaimTranslation(budget=RecordingBudget(), runner=runner)

    translation.english_queries(RUSSIAN_CLAIMS, "ru")

    assert runner.calls[0]["allowed_tools"] == ()
    assert "1. Сортировка слиянием работает за O(n log n)" in str(runner.calls[0]["prompt"])
    assert "2. Число Пи иррационально" in str(runner.calls[0]["prompt"])


def test_translation_charges_the_budget() -> None:
    budget = RecordingBudget()
    translation = ClaudeCliClaimTranslation(
        budget=budget, runner=FakeRunner(a_translation(english_queries(), cost_usd=0.02))
    )

    translation.english_queries(RUSSIAN_CLAIMS, "ru")

    assert budget.charges == [0.02]


def test_translation_retries_a_wrong_query_count_once() -> None:
    runner = FakeRunner(a_translation(["only one"]), a_translation(english_queries()))
    translation = ClaudeCliClaimTranslation(budget=RecordingBudget(), runner=runner)

    queries = translation.english_queries(RUSSIAN_CLAIMS, "ru")

    assert len(runner.calls) == 2
    assert queries == english_queries()


def test_translation_fails_after_a_second_schema_mismatch() -> None:
    blank = a_translation(["merge sort", ""])
    translation = ClaudeCliClaimTranslation(budget=RecordingBudget(), runner=FakeRunner(blank, blank))

    with pytest.raises(FactcheckResponseError, match="queries"):
        translation.english_queries(RUSSIAN_CLAIMS, "ru")
