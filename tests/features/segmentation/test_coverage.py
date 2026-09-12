# @covers analysis:INV-020
import pytest

from konspekt.features.segmentation.application.coverage import (
    TimelineCoverageError,
    validate_timeline_coverage,
)
from konspekt.features.segmentation.domain.segments import LabeledSpan, SpanLabel
from konspekt.shared.timecode import TimeRange


def a_core_span(start_seconds: float, end_seconds: float) -> LabeledSpan:
    return LabeledSpan(
        time_range=TimeRange(start_seconds, end_seconds),
        label=SpanLabel.CORE,
        section_id="s1",
        reason=None,
    )


def test_exact_partition_of_timeline_is_accepted() -> None:
    spans = [a_core_span(0.0, 60.0), a_core_span(60.0, 120.0)]

    validate_timeline_coverage(spans, TimeRange(0.0, 120.0))


def test_gap_of_one_second_is_rejected_with_gap_position() -> None:
    spans = [a_core_span(0.0, 60.0), a_core_span(61.0, 120.0)]

    with pytest.raises(TimelineCoverageError, match="60") as raised:
        validate_timeline_coverage(spans, TimeRange(0.0, 120.0))

    assert raised.value.position_seconds == 60.0


def test_gap_of_exactly_half_second_is_within_tolerance() -> None:
    spans = [a_core_span(0.0, 60.0), a_core_span(60.5, 120.0)]

    validate_timeline_coverage(spans, TimeRange(0.0, 120.0))


def test_overlap_beyond_tolerance_is_rejected() -> None:
    spans = [a_core_span(0.0, 60.0), a_core_span(59.0, 120.0)]

    with pytest.raises(TimelineCoverageError) as raised:
        validate_timeline_coverage(spans, TimeRange(0.0, 120.0))

    assert raised.value.position_seconds == 59.0


def test_first_span_starting_after_timeline_start_is_rejected() -> None:
    spans = [a_core_span(2.0, 120.0)]

    with pytest.raises(TimelineCoverageError) as raised:
        validate_timeline_coverage(spans, TimeRange(0.0, 120.0))

    assert raised.value.position_seconds == 0.0


def test_last_span_ending_before_timeline_end_is_rejected() -> None:
    spans = [a_core_span(0.0, 118.0)]

    with pytest.raises(TimelineCoverageError) as raised:
        validate_timeline_coverage(spans, TimeRange(0.0, 120.0))

    assert raised.value.position_seconds == 118.0


def test_empty_span_list_is_rejected() -> None:
    with pytest.raises(TimelineCoverageError) as raised:
        validate_timeline_coverage([], TimeRange(0.0, 120.0))

    assert raised.value.position_seconds == 0.0
