# @covers analysis:INV-020
import pytest

from konspekt.features.segmentation.application.snap import (
    SNAP_TOLERANCE_SECONDS,
    snap_spans_to_timeline,
)
from konspekt.features.segmentation.domain.segments import LabeledSpan, SpanLabel
from konspekt.features.transcription.domain.transcript import TranscriptSegment
from konspekt.shared.timecode import TimeRange


def core_span(start: float, end: float) -> LabeledSpan:
    return LabeledSpan(TimeRange(start, end), SpanLabel.CORE, "s1", None)


def a_segment(start: float, end: float) -> TranscriptSegment:
    return TranscriptSegment(TimeRange(start, end), "speech", None)


def test_edges_are_snapped_to_the_timeline_bounds() -> None:
    spans = [core_span(1.2, 300.0), core_span(300.0, 719.0)]
    segments = [a_segment(1.2, 300.0), a_segment(300.0, 719.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.1), segments)

    assert snapped[0].time_range.start_seconds == 0.0
    assert snapped[-1].time_range.end_seconds == 720.1


def test_small_internal_gap_is_closed_by_extending_the_earlier_span() -> None:
    spans = [core_span(0.0, 300.0), core_span(303.0, 720.0)]
    segments = [a_segment(0.0, 300.0), a_segment(303.0, 720.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.0), segments)

    assert snapped[0].time_range.end_seconds == 303.0
    assert snapped[1].time_range.start_seconds == 303.0


def test_small_overlap_is_trimmed_on_the_earlier_span() -> None:
    spans = [core_span(0.0, 305.0), core_span(303.0, 720.0)]
    segments = [a_segment(0.0, 303.0), a_segment(303.0, 720.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.0), segments)

    assert snapped[0].time_range.end_seconds == 303.0


def test_internal_gap_with_speech_inside_is_closed_by_extending_the_earlier_span() -> None:
    wide_gap = SNAP_TOLERANCE_SECONDS + 5.0
    spans = [core_span(0.0, 300.0), core_span(300.0 + wide_gap, 720.0)]
    segments = [
        a_segment(0.0, 300.0),
        a_segment(300.0, 300.0 + wide_gap),
        a_segment(300.0 + wide_gap, 720.0),
    ]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.0), segments)

    assert snapped[0].time_range.end_seconds == 300.0 + wide_gap
    assert snapped[1].time_range.start_seconds == 300.0 + wide_gap


def test_unlabeled_tail_with_speech_becomes_an_admin_span() -> None:
    spans = [core_span(0.0, 7230.0)]
    segments = [a_segment(0.0, 7230.0), a_segment(7231.0, 7268.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 7268.0), segments)

    assert snapped[0].time_range.end_seconds == 7230.0
    assert snapped[1].time_range == TimeRange(7230.0, 7268.0)
    assert snapped[1].label is SpanLabel.ADMIN
    assert snapped[1].section_id is None
    assert snapped[1].reason is not None


def test_unlabeled_head_with_speech_becomes_an_admin_span() -> None:
    spans = [core_span(40.0, 720.0)]
    segments = [a_segment(0.0, 39.0), a_segment(40.0, 720.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.0), segments)

    assert snapped[0].time_range == TimeRange(0.0, 40.0)
    assert snapped[0].label is SpanLabel.ADMIN
    assert snapped[1].time_range.start_seconds == 40.0


def test_silent_gap_is_closed_regardless_of_size() -> None:
    spans = [core_span(0.0, 300.0), core_span(600.0, 720.0)]
    segments = [a_segment(0.0, 300.0), a_segment(600.0, 720.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.0), segments)

    assert snapped[0].time_range.end_seconds == 600.0
    assert snapped[1].time_range.start_seconds == 600.0


def test_silent_edges_snap_without_tolerance_limit() -> None:
    spans = [core_span(100.0, 300.0)]
    segments = [a_segment(100.0, 300.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 400.0), segments)

    assert snapped[0].time_range.start_seconds == 0.0
    assert snapped[0].time_range.end_seconds == 400.0


def test_labels_and_reasons_survive_snapping() -> None:
    spans = [
        LabeledSpan(TimeRange(1.0, 300.0), SpanLabel.TANGENT, None, "байка"),
        core_span(300.0, 719.0),
    ]
    segments = [a_segment(1.0, 300.0), a_segment(300.0, 719.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.0), segments)

    assert snapped[0].label is SpanLabel.TANGENT
    assert snapped[0].reason == "байка"


def test_unsorted_input_is_sorted_by_start() -> None:
    spans = [core_span(300.0, 720.0), core_span(0.0, 300.0)]
    segments = [a_segment(0.0, 300.0), a_segment(300.0, 720.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.0), segments)

    assert [span.time_range.start_seconds for span in snapped] == [0.0, 300.0]


def test_empty_spans_raise() -> None:
    with pytest.raises(ValueError, match="no spans"):
        snap_spans_to_timeline([], TimeRange(0.0, 720.0), [])


def test_span_overshooting_the_timeline_end_is_clamped() -> None:
    spans = [core_span(0.0, 300.0), core_span(300.0, 9282.0)]
    segments = [a_segment(0.0, 300.0), a_segment(300.0, 720.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.0), segments)

    assert snapped[-1].time_range.end_seconds == 720.0


def test_span_entirely_outside_the_timeline_is_dropped() -> None:
    spans = [core_span(0.0, 720.0), core_span(800.0, 900.0)]
    segments = [a_segment(0.0, 720.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.0), segments)

    assert len(snapped) == 1
    assert snapped[0].time_range.end_seconds == 720.0


def test_large_overlap_is_trimmed_on_the_earlier_span() -> None:
    spans = [core_span(0.0, 130.0), core_span(120.5, 720.0)]
    segments = [a_segment(0.0, 120.0), a_segment(121.0, 720.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.0), segments)

    assert snapped[0].time_range.end_seconds == 120.5
    assert snapped[1].time_range.start_seconds == 120.5


def test_span_contained_in_the_previous_one_is_dropped() -> None:
    spans = [core_span(0.0, 300.0), core_span(120.0, 200.0), core_span(300.0, 720.0)]
    segments = [a_segment(0.0, 300.0), a_segment(300.0, 720.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.0), segments)

    assert [(span.time_range.start_seconds, span.time_range.end_seconds) for span in snapped] == [
        (0.0, 300.0),
        (300.0, 720.0),
    ]


def test_earlier_span_swallowed_by_a_later_start_is_dropped() -> None:
    spans = [core_span(0.0, 100.0), core_span(100.0, 110.0), core_span(100.0, 720.0)]
    segments = [a_segment(0.0, 100.0), a_segment(100.0, 720.0)]

    snapped = snap_spans_to_timeline(spans, TimeRange(0.0, 720.0), segments)

    assert [(span.time_range.start_seconds, span.time_range.end_seconds) for span in snapped] == [
        (0.0, 100.0),
        (100.0, 720.0),
    ]
