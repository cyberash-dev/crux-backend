# @covers analysis:CON-020
# @covers analysis:DLT-024
import pytest

from konspekt.features.segmentation.application.artifact import (
    SegmentationPayloadError,
    parse_segmentation_payload,
    segmentation_payload,
)
from konspekt.features.segmentation.domain.segments import (
    LabeledSpan,
    SectionPlanEntry,
    SegmentationResult,
    SpanLabel,
)
from konspekt.shared.timecode import TimeRange


def a_segmentation_result() -> SegmentationResult:
    return SegmentationResult(
        lecture_title="Введение в анализ",
        sections_plan=(
            SectionPlanEntry(
                "s1",
                "Limits",
                TimeRange(0.0, 600.0),
                subsections=(
                    SectionPlanEntry("s1.1", "Definition", TimeRange(0.0, 300.0)),
                    SectionPlanEntry("s1.2", "Examples", TimeRange(300.0, 600.0)),
                ),
            ),
            SectionPlanEntry("s2", "Derivatives", TimeRange(600.0, 1200.0)),
        ),
        spans=(
            LabeledSpan(TimeRange(0.0, 500.0), SpanLabel.CORE, "s1.1", None),
            LabeledSpan(TimeRange(500.0, 600.0), SpanLabel.ANECDOTE, None, "joke"),
            LabeledSpan(TimeRange(600.0, 1200.0), SpanLabel.CORE, "s2", None),
        ),
    )


def test_nested_payload_round_trips_through_parse() -> None:
    original = a_segmentation_result()

    restored = parse_segmentation_payload(segmentation_payload(original))

    assert restored == original


def test_payload_uses_contract_field_names() -> None:
    payload = segmentation_payload(a_segmentation_result())

    assert payload["lecture_title"] == "Введение в анализ"
    assert payload["sections_plan"][0]["section_id"] == "s1"
    assert payload["sections_plan"][0]["subsections"][0] == {
        "section_id": "s1.1",
        "title": "Definition",
        "start_seconds": 0.0,
        "end_seconds": 300.0,
        "subsections": [],
    }
    assert payload["spans"][1] == {
        "start_seconds": 500.0,
        "end_seconds": 600.0,
        "label": "anecdote",
        "section_id": None,
        "reason": "joke",
    }


def test_non_core_span_with_null_reason_is_rejected() -> None:
    payload = segmentation_payload(a_segmentation_result())
    payload["spans"][1]["reason"] = None

    with pytest.raises(SegmentationPayloadError, match="reason"):
        parse_segmentation_payload(payload)


def test_unknown_label_is_rejected() -> None:
    payload = segmentation_payload(a_segmentation_result())
    payload["spans"][0]["label"] = "filler"

    with pytest.raises(SegmentationPayloadError, match="filler"):
        parse_segmentation_payload(payload)


def test_missing_lecture_title_is_rejected() -> None:
    payload = segmentation_payload(a_segmentation_result())
    del payload["lecture_title"]

    with pytest.raises(SegmentationPayloadError, match="lecture_title"):
        parse_segmentation_payload(payload)


def test_duplicate_section_id_across_the_plan_tree_is_rejected() -> None:
    payload = segmentation_payload(a_segmentation_result())
    payload["sections_plan"][0]["subsections"][0]["section_id"] = "s2"

    with pytest.raises(SegmentationPayloadError, match="'s2'"):
        parse_segmentation_payload(payload)


def test_plan_nesting_deeper_than_two_levels_is_rejected() -> None:
    payload = segmentation_payload(a_segmentation_result())
    payload["sections_plan"][0]["subsections"][0]["subsections"] = [
        {
            "section_id": "s1.1.1",
            "title": "Too deep",
            "start_seconds": 0.0,
            "end_seconds": 100.0,
            "subsections": [],
        }
    ]

    with pytest.raises(SegmentationPayloadError, match="depth"):
        parse_segmentation_payload(payload)
