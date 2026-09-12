# @covers analysis:EXT-011
import json
from typing import Any

import pytest

from konspekt.features.segmentation.adapters.outbound.claude_cli_segmentation import (
    ClaudeCliSegmentation,
)
from konspekt.features.segmentation.adapters.outbound.text_protocol import (
    SegmentationResponseFormatError,
)
from konspekt.features.segmentation.domain.segments import SectionPlanEntry
from konspekt.features.transcription.domain.transcript import (
    Transcript,
    TranscriptSegment,
)
from konspekt.shared.claude_cli import ClaudeCliError, ClaudeCliResult
from konspekt.shared.timecode import TimeRange


class FakeCliRunner:
    def __init__(self, results: list[ClaudeCliResult]) -> None:
        self._results = list(results)
        self.run_requests: list[dict[str, Any]] = []

    def run(
        self, prompt: str, model: str, allowed_tools: tuple[str, ...] = ()
    ) -> ClaudeCliResult:
        self.run_requests.append(
            {"prompt": prompt, "model": model, "allowed_tools": allowed_tools}
        )
        return self._results.pop(0)


class RaisingCliRunner:
    def run(
        self, prompt: str, model: str, allowed_tools: tuple[str, ...] = ()
    ) -> ClaudeCliResult:
        raise ClaudeCliError("claude exited with 1: boom")


class RecordingBudget:
    def __init__(self) -> None:
        self.charged_costs_usd: list[float] = []

    def charge(self, cost_usd: float) -> None:
        self.charged_costs_usd.append(cost_usd)


def a_transcript() -> Transcript:
    return Transcript(
        language="ru",
        segments=(
            TranscriptSegment(TimeRange(0.0, 600.0), "limits definition", None),
            TranscriptSegment(TimeRange(600.0, 1200.0), "epsilon delta", None),
        ),
    )


def a_two_window_transcript() -> Transcript:
    return Transcript(
        language="ru",
        segments=(
            TranscriptSegment(TimeRange(0.0, 1700.0), "first half", None),
            TranscriptSegment(TimeRange(1800.0, 3600.0), "second half", None),
        ),
    )


def a_section_plan() -> list[SectionPlanEntry]:
    return [SectionPlanEntry("s1", "Limits", TimeRange(0.0, 1200.0))]


def plan_json_text() -> str:
    return json.dumps(
        {
            "lecture_title": "Введение в анализ",
            "sections": [
                {
                    "section_id": "s1",
                    "title": "Limits",
                    "start_seconds": 0.0,
                    "end_seconds": 1200.0,
                    "subsections": [],
                }
            ],
        }
    )


def spans_json_text(start_seconds: float, end_seconds: float) -> str:
    return json.dumps(
        {
            "spans": [
                {
                    "start_seconds": start_seconds,
                    "end_seconds": end_seconds,
                    "label": "core",
                    "section_id": "s1",
                    "reason": None,
                }
            ]
        }
    )


def a_result(text: str, cost_usd: float = 0.05) -> ClaudeCliResult:
    return ClaudeCliResult(text=text, cost_usd=cost_usd)


def test_plan_shape_hint_names_lecture_title_and_subsections() -> None:
    runner = FakeCliRunner([a_result(plan_json_text())])
    adapter = ClaudeCliSegmentation(budget=RecordingBudget(), runner=runner)

    adapter.plan_outline(a_transcript())

    assert "lecture_title" in runner.run_requests[0]["prompt"]
    assert "subsections" in runner.run_requests[0]["prompt"]


def test_plan_outline_sends_timecoded_prompt_to_runner() -> None:
    runner = FakeCliRunner([a_result(plan_json_text())])
    adapter = ClaudeCliSegmentation(budget=RecordingBudget(), runner=runner)

    adapter.plan_outline(a_transcript())

    assert "[00:00:00] limits definition" in runner.run_requests[0]["prompt"]


def test_prompt_demands_single_json_object_without_fences() -> None:
    runner = FakeCliRunner([a_result(plan_json_text())])
    adapter = ClaudeCliSegmentation(budget=RecordingBudget(), runner=runner)

    adapter.plan_outline(a_transcript())

    assert "exactly one JSON object" in runner.run_requests[0]["prompt"]
    assert "markdown" in runner.run_requests[0]["prompt"]


def test_model_from_constructor_is_forwarded_to_runner() -> None:
    runner = FakeCliRunner([a_result(plan_json_text())])
    adapter = ClaudeCliSegmentation(
        budget=RecordingBudget(), model="claude-sonnet-5", runner=runner
    )

    adapter.plan_outline(a_transcript())

    assert runner.run_requests[0]["model"] == "claude-sonnet-5"


def test_plan_outline_returns_title_and_parsed_entries() -> None:
    runner = FakeCliRunner([a_result(plan_json_text())])
    adapter = ClaudeCliSegmentation(budget=RecordingBudget(), runner=runner)

    lecture_title, entries = adapter.plan_outline(a_transcript())

    assert lecture_title == "Введение в анализ"
    assert entries == a_section_plan()


def test_budget_is_charged_with_cost_from_cli_result() -> None:
    budget = RecordingBudget()
    runner = FakeCliRunner([a_result(plan_json_text(), cost_usd=0.42)])
    adapter = ClaudeCliSegmentation(budget=budget, runner=runner)

    adapter.plan_outline(a_transcript())

    assert budget.charged_costs_usd == [pytest.approx(0.42)]


def test_fenced_response_with_prose_is_parsed() -> None:
    fenced_text = f"Here is the plan:\n```json\n{plan_json_text()}\n```\nDone."
    runner = FakeCliRunner([a_result(fenced_text)])
    adapter = ClaudeCliSegmentation(budget=RecordingBudget(), runner=runner)

    lecture_title, entries = adapter.plan_outline(a_transcript())

    assert entries == a_section_plan()


def test_invalid_response_is_retried_once_with_both_runs_charged() -> None:
    budget = RecordingBudget()
    runner = FakeCliRunner(
        [a_result("no json here", cost_usd=0.1), a_result(plan_json_text(), cost_usd=0.2)]
    )
    adapter = ClaudeCliSegmentation(budget=budget, runner=runner)

    lecture_title, entries = adapter.plan_outline(a_transcript())

    assert entries == a_section_plan()
    assert len(runner.run_requests) == 2
    assert budget.charged_costs_usd == [pytest.approx(0.1), pytest.approx(0.2)]


def test_two_invalid_responses_raise_typed_error() -> None:
    runner = FakeCliRunner([a_result("no json here"), a_result("{\"still\": \"wrong\"}")])
    adapter = ClaudeCliSegmentation(budget=RecordingBudget(), runner=runner)

    with pytest.raises(SegmentationResponseFormatError):
        adapter.plan_outline(a_transcript())

    assert len(runner.run_requests) == 2


def test_cli_error_propagates_unwrapped() -> None:
    adapter = ClaudeCliSegmentation(
        budget=RecordingBudget(), runner=RaisingCliRunner()
    )

    with pytest.raises(ClaudeCliError, match="boom"):
        adapter.plan_outline(a_transcript())


def test_label_spans_runs_each_window_and_merges_results() -> None:
    runner = FakeCliRunner(
        [
            a_result(spans_json_text(0.0, 1800.0)),
            a_result(spans_json_text(1800.0, 3600.0)),
        ]
    )
    adapter = ClaudeCliSegmentation(budget=RecordingBudget(), runner=runner)

    spans = adapter.label_spans(a_two_window_transcript(), a_section_plan())

    assert [span.time_range.start_seconds for span in spans] == [0.0, 1800.0]
    assert len(runner.run_requests) == 2
    assert "Limits" in runner.run_requests[0]["prompt"]
