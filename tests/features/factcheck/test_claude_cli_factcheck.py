# @covers analysis:EXT-011
import json

import pytest

from konspekt.features.factcheck.adapters.outbound.claude_cli_factcheck import (
    ClaudeCliClaimExtraction,
)
from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    FactcheckResponseError,
)
from konspekt.features.factcheck.domain.claims import ExtractedClaim
from konspekt.shared.claude_cli import ClaudeCliResult
from konspekt.shared.timecode import TimeRange


class FakeRunner:
    def __init__(self, *results: ClaudeCliResult) -> None:
        self._results = list(results)
        self.calls: list[dict[str, object]] = []

    def run(
        self, prompt: str, model: str, allowed_tools: tuple[str, ...] = ()
    ) -> ClaudeCliResult:
        self.calls.append(
            {"prompt": prompt, "model": model, "allowed_tools": allowed_tools}
        )
        return self._results[len(self.calls) - 1]


class RecordingBudget:
    def __init__(self) -> None:
        self.charges: list[float] = []

    def charge(self, cost_usd: float) -> None:
        self.charges.append(cost_usd)


def an_extraction_result(cost_usd: float = 0.04) -> ClaudeCliResult:
    return ClaudeCliResult(
        text=json.dumps(
            {
                "claims": [
                    {
                        "claim_text": "Скорость света — 300 000 км/с",
                        "span_start_seconds": 12.5,
                        "span_end_seconds": 40.0,
                    }
                ]
            }
        ),
        cost_usd=cost_usd,
    )


def test_extraction_parses_claims_and_charges_reported_cost() -> None:
    runner = FakeRunner(an_extraction_result(cost_usd=0.04))
    budget = RecordingBudget()
    extraction = ClaudeCliClaimExtraction(budget=budget, runner=runner)

    claims = extraction.extract_claims("[00:00:12] core text", "ru")

    assert claims == [
        ExtractedClaim(
            claim_text="Скорость света — 300 000 км/с",
            span=TimeRange(12.5, 40.0),
        )
    ]
    assert budget.charges == [pytest.approx(0.04)]


def test_extraction_grants_no_tools_and_forwards_model() -> None:
    runner = FakeRunner(an_extraction_result())
    extraction = ClaudeCliClaimExtraction(
        budget=RecordingBudget(), model="claude-opus-4-8", runner=runner
    )

    extraction.extract_claims("core text", "en")

    assert runner.calls[0]["allowed_tools"] == ()
    assert runner.calls[0]["model"] == "claude-opus-4-8"


def test_extraction_prompt_carries_language_and_transcript() -> None:
    runner = FakeRunner(an_extraction_result())
    extraction = ClaudeCliClaimExtraction(budget=RecordingBudget(), runner=runner)

    extraction.extract_claims("[00:00:12] the core text", "ru")

    prompt = runner.calls[0]["prompt"]
    assert isinstance(prompt, str)
    assert "[00:00:12] the core text" in prompt
    assert "ru" in prompt


def test_extraction_schema_mismatch_is_retried_once_and_succeeds() -> None:
    runner = FakeRunner(
        ClaudeCliResult(text="{not json", cost_usd=0.02),
        an_extraction_result(cost_usd=0.05),
    )
    budget = RecordingBudget()
    extraction = ClaudeCliClaimExtraction(budget=budget, runner=runner)

    claims = extraction.extract_claims("core text", "ru")

    assert len(claims) == 1
    assert len(runner.calls) == 2
    assert budget.charges == [pytest.approx(0.02), pytest.approx(0.05)]


def test_extraction_schema_mismatch_twice_fails_after_two_runs() -> None:
    runner = FakeRunner(
        ClaudeCliResult(text="{not json", cost_usd=0.02),
        ClaudeCliResult(text='{"unexpected": "shape"}', cost_usd=0.02),
    )
    extraction = ClaudeCliClaimExtraction(budget=RecordingBudget(), runner=runner)

    with pytest.raises(FactcheckResponseError, match="claims"):
        extraction.extract_claims("core text", "ru")

    assert len(runner.calls) == 2
