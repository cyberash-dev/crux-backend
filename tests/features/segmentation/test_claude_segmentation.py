# @covers analysis:EXT-010
import json
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any

import pytest

from konspekt.features.segmentation.adapters.outbound.claude_segmentation import (
    ClaudeSegmentation,
    SegmentationRefusalError,
    SegmentationResponseFormatError,
    label_spans_prompt,
    merge_span_windows,
    parse_labeled_spans,
    parse_plan_outline,
    plan_outline_prompt,
    transcript_windows,
    usage_cost_usd,
)
from konspekt.features.segmentation.domain.segments import (
    LabeledSpan,
    SectionPlanEntry,
    SpanLabel,
)
from konspekt.features.transcription.domain.transcript import (
    Transcript,
    TranscriptSegment,
)
from konspekt.shared.timecode import TimeRange


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeMessage:
    content: list[FakeTextBlock]
    usage: FakeUsage
    stop_reason: str = "end_turn"


class FakeMessageStream:
    def __init__(self, message: FakeMessage) -> None:
        self._message = message

    def __enter__(self) -> "FakeMessageStream":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def get_final_message(self) -> FakeMessage:
        return self._message


@dataclass
class FakeMessagesApi:
    responses: list[FakeMessage]
    create_requests: list[dict[str, Any]] = field(default_factory=list)
    stream_requests: list[dict[str, Any]] = field(default_factory=list)

    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, str]],
        output_config: dict[str, Any],
    ) -> FakeMessage:
        self.create_requests.append(
            {"model": model, "max_tokens": max_tokens, "messages": messages}
        )
        return self.responses.pop(0)

    def stream(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, str]],
        output_config: dict[str, Any],
    ) -> FakeMessageStream:
        self.stream_requests.append(
            {"model": model, "max_tokens": max_tokens, "messages": messages}
        )
        return FakeMessageStream(self.responses.pop(0))


class FakeClaudeClient:
    def __init__(self, responses: list[FakeMessage]) -> None:
        self.messages = FakeMessagesApi(responses)


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
                    "subsections": [
                        {
                            "section_id": "s1.1",
                            "title": "Definition",
                            "start_seconds": 0.0,
                            "end_seconds": 600.0,
                            "subsections": [],
                        }
                    ],
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


def a_message(text: str, usage: FakeUsage | None = None) -> FakeMessage:
    return FakeMessage(
        content=[FakeTextBlock(text)], usage=usage or FakeUsage(100, 10)
    )


def a_section_plan() -> list[SectionPlanEntry]:
    return [
        SectionPlanEntry(
            "s1",
            "Limits",
            TimeRange(0.0, 1200.0),
            subsections=(
                SectionPlanEntry("s1.1", "Definition", TimeRange(0.0, 600.0)),
            ),
        )
    ]


def test_plan_outline_prompt_contains_timecoded_transcript() -> None:
    prompt = plan_outline_prompt(a_transcript())

    assert "[00:00:00] limits definition" in prompt
    assert "[00:10:00] epsilon delta" in prompt


def test_plan_outline_prompt_demands_grouped_hierarchy_and_title() -> None:
    prompt = plan_outline_prompt(a_transcript())

    assert "lecture_title" in prompt
    assert "5-10" in prompt
    assert "never more than 12" in prompt
    assert "subsections" in prompt


def test_label_spans_prompt_contains_plan_window_and_conservative_rule() -> None:
    window = a_transcript().segments

    prompt = label_spans_prompt(window, a_section_plan())

    assert "Limits" in prompt
    assert "[00:00:00] limits definition" in prompt
    assert "label the span core" in prompt


def test_label_spans_prompt_lists_subsections_and_demands_leaf_ids() -> None:
    window = a_transcript().segments

    prompt = label_spans_prompt(window, a_section_plan())

    assert "s1.1" in prompt
    assert "most specific" in prompt


def test_parse_plan_outline_builds_title_and_nested_entries() -> None:
    lecture_title, entries = parse_plan_outline(json.loads(plan_json_text()))

    assert lecture_title == "Введение в анализ"
    assert entries == a_section_plan()


def test_parse_plan_outline_rejects_payload_without_sections() -> None:
    with pytest.raises(SegmentationResponseFormatError, match="sections"):
        parse_plan_outline({"lecture_title": "x", "unexpected": []})


def test_parse_plan_outline_rejects_missing_lecture_title() -> None:
    with pytest.raises(SegmentationResponseFormatError, match="lecture_title"):
        parse_plan_outline({"sections": []})


def test_parse_plan_outline_rejects_duplicate_section_ids() -> None:
    payload = json.loads(plan_json_text())
    payload["sections"][0]["subsections"][0]["section_id"] = "s1"

    with pytest.raises(SegmentationResponseFormatError, match="'s1'"):
        parse_plan_outline(payload)


def test_parse_plan_outline_rejects_nesting_deeper_than_two_levels() -> None:
    payload = json.loads(plan_json_text())
    payload["sections"][0]["subsections"][0]["subsections"] = [
        {
            "section_id": "s1.1.1",
            "title": "Too deep",
            "start_seconds": 0.0,
            "end_seconds": 100.0,
            "subsections": [],
        }
    ]

    with pytest.raises(SegmentationResponseFormatError, match="depth"):
        parse_plan_outline(payload)


def test_parse_labeled_spans_builds_spans_from_json_payload() -> None:
    spans = parse_labeled_spans(json.loads(spans_json_text(0.0, 1200.0)))

    assert spans == [LabeledSpan(TimeRange(0.0, 1200.0), SpanLabel.CORE, "s1", None)]


def test_parse_labeled_spans_rejects_unknown_label() -> None:
    payload = {
        "spans": [
            {
                "start_seconds": 0.0,
                "end_seconds": 10.0,
                "label": "filler",
                "section_id": None,
                "reason": "x",
            }
        ]
    }

    with pytest.raises(SegmentationResponseFormatError, match="filler"):
        parse_labeled_spans(payload)


def test_parse_labeled_spans_rejects_non_core_span_without_reason() -> None:
    payload = {
        "spans": [
            {
                "start_seconds": 0.0,
                "end_seconds": 10.0,
                "label": "tangent",
                "section_id": None,
                "reason": None,
            }
        ]
    }

    with pytest.raises(SegmentationResponseFormatError, match="reason"):
        parse_labeled_spans(payload)


def test_transcript_windows_split_at_thirty_minutes() -> None:
    windows = transcript_windows(a_two_window_transcript())

    assert [
        [segment.text for segment in window] for window in windows
    ] == [["first half"], ["second half"]]


def test_transcript_windows_keep_short_transcript_whole() -> None:
    windows = transcript_windows(a_transcript())

    assert len(windows) == 1


def test_merge_span_windows_orders_spans_by_start() -> None:
    late = LabeledSpan(TimeRange(1800.0, 3600.0), SpanLabel.CORE, "s1", None)
    early = LabeledSpan(TimeRange(0.0, 1800.0), SpanLabel.CORE, "s1", None)

    merged = merge_span_windows([[late], [early]])

    assert merged == [early, late]


def test_usage_cost_follows_opus_five_pricing() -> None:
    assert usage_cost_usd(1_000_000, 0) == pytest.approx(5.0)
    assert usage_cost_usd(0, 1_000_000) == pytest.approx(25.0)


def test_budget_is_charged_with_cost_from_reported_usage() -> None:
    budget = RecordingBudget()
    client = FakeClaudeClient([a_message(plan_json_text(), FakeUsage(1000, 200))])
    adapter = ClaudeSegmentation(budget=budget, client=client)

    adapter.plan_outline(a_transcript())

    assert budget.charged_costs_usd == [pytest.approx(0.01)]


def test_plan_outline_returns_title_and_parsed_entries() -> None:
    client = FakeClaudeClient([a_message(plan_json_text())])
    adapter = ClaudeSegmentation(budget=RecordingBudget(), client=client)

    lecture_title, entries = adapter.plan_outline(a_transcript())

    assert lecture_title == "Введение в анализ"
    assert entries == a_section_plan()


def test_label_spans_streams_each_window_and_merges_results() -> None:
    client = FakeClaudeClient(
        [
            a_message(spans_json_text(0.0, 1800.0)),
            a_message(spans_json_text(1800.0, 3600.0)),
        ]
    )
    adapter = ClaudeSegmentation(budget=RecordingBudget(), client=client)

    spans = adapter.label_spans(a_two_window_transcript(), a_section_plan())

    assert [span.time_range.start_seconds for span in spans] == [0.0, 1800.0]
    assert len(client.messages.stream_requests) == 2
    assert client.messages.create_requests == []


def test_refusal_stop_reason_raises_typed_error() -> None:
    refusal = FakeMessage(
        content=[], usage=FakeUsage(100, 0), stop_reason="refusal"
    )
    adapter = ClaudeSegmentation(
        budget=RecordingBudget(), client=FakeClaudeClient([refusal])
    )

    with pytest.raises(SegmentationRefusalError, match="refus"):
        adapter.plan_outline(a_transcript())


def test_schema_mismatch_is_retried_once_with_second_response_used() -> None:
    client = FakeClaudeClient(
        [a_message("not json at all"), a_message(plan_json_text())]
    )
    adapter = ClaudeSegmentation(budget=RecordingBudget(), client=client)

    lecture_title, entries = adapter.plan_outline(a_transcript())

    assert entries == a_section_plan()
    assert len(client.messages.create_requests) == 2


def test_schema_mismatch_twice_raises_typed_error() -> None:
    client = FakeClaudeClient(
        [a_message("not json at all"), a_message("{\"still\": \"wrong\"}")]
    )
    adapter = ClaudeSegmentation(budget=RecordingBudget(), client=client)

    with pytest.raises(SegmentationResponseFormatError):
        adapter.plan_outline(a_transcript())

    assert len(client.messages.create_requests) == 2
