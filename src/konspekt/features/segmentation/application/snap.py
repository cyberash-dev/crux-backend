from collections.abc import Sequence
from dataclasses import replace

from konspekt.features.segmentation.domain.segments import LabeledSpan, SpanLabel
from konspekt.features.transcription.domain.transcript import TranscriptSegment
from konspekt.shared.timecode import TimeRange

SNAP_TOLERANCE_SECONDS = 5.0
UNLABELED_EDGE_REASON = "not labeled by the model; excluded from the notes"


def snap_spans_to_timeline(
    spans: Sequence[LabeledSpan],
    timeline: TimeRange,
    segments: Sequence[TranscriptSegment],
) -> list[LabeledSpan]:
    """LLM span boundaries follow utterance timecodes and drift by a few
    seconds from the exact timeline; snapping keeps analysis:INV-020 intact
    without weakening its 0.5 s validation tolerance. A gap holding no
    transcript-segment midpoint is silence (a break), not lost material,
    so it closes regardless of size; an internal gap holding speech is
    treated as continuation of the earlier span. Overlaps are resolved in
    favour of the later span's start: the earlier span is trimmed, and a
    span fully covered by its predecessor is dropped. Speech the model left
    unlabeled at the head or tail becomes an admin span, so it lands in
    the cut log instead of failing the run."""
    if not spans:
        raise ValueError("no spans to snap")
    midpoints = [
        (segment.time_range.start_seconds + segment.time_range.end_seconds) / 2
        for segment in segments
    ]
    clamped = [span for span in (_clamped_to(span, timeline) for span in spans) if span]
    if not clamped:
        raise ValueError("no spans left inside the timeline")
    ordered = sorted(clamped, key=lambda span: span.time_range.start_seconds)
    snapped: list[LabeledSpan] = []
    for index, span in enumerate(ordered):
        start = span.time_range.start_seconds
        end = span.time_range.end_seconds
        if index == 0 and _is_boundary_snappable(
            timeline.start_seconds, start, midpoints
        ):
            start = timeline.start_seconds
        if index == len(ordered) - 1 and _is_boundary_snappable(
            end, timeline.end_seconds, midpoints
        ):
            end = timeline.end_seconds
        if snapped and _is_contained_in_previous(snapped[-1], end):
            continue
        while snapped and start <= snapped[-1].time_range.start_seconds:
            snapped.pop()
        if snapped and start != snapped[-1].time_range.end_seconds:
            snapped[-1] = _with_end(snapped[-1], start)
        snapped.append(_with_range(span, start, end))
    return _with_unlabeled_edges(snapped, timeline)


def _with_unlabeled_edges(spans: list[LabeledSpan], timeline: TimeRange) -> list[LabeledSpan]:
    head_end = spans[0].time_range.start_seconds
    tail_start = spans[-1].time_range.end_seconds
    head = (
        [_unlabeled_span(timeline.start_seconds, head_end)]
        if head_end > timeline.start_seconds
        else []
    )
    tail = (
        [_unlabeled_span(tail_start, timeline.end_seconds)]
        if tail_start < timeline.end_seconds
        else []
    )
    return head + spans + tail


def _unlabeled_span(start_seconds: float, end_seconds: float) -> LabeledSpan:
    return LabeledSpan(
        time_range=TimeRange(start_seconds, end_seconds),
        label=SpanLabel.ADMIN,
        section_id=None,
        reason=UNLABELED_EDGE_REASON,
    )


def _is_contained_in_previous(previous: LabeledSpan, end_seconds: float) -> bool:
    return end_seconds <= previous.time_range.end_seconds


def _clamped_to(span: LabeledSpan, timeline: TimeRange) -> LabeledSpan | None:
    start = max(span.time_range.start_seconds, timeline.start_seconds)
    end = min(span.time_range.end_seconds, timeline.end_seconds)
    if start >= end:
        return None
    if (start, end) == (span.time_range.start_seconds, span.time_range.end_seconds):
        return span
    return _with_range(span, start, end)


def _is_boundary_snappable(
    earlier_seconds: float, later_seconds: float, midpoints: Sequence[float]
) -> bool:
    if abs(later_seconds - earlier_seconds) <= SNAP_TOLERANCE_SECONDS:
        return True
    if later_seconds < earlier_seconds:
        return False
    return not any(
        earlier_seconds <= midpoint < later_seconds for midpoint in midpoints
    )


def _with_end(span: LabeledSpan, end_seconds: float) -> LabeledSpan:
    return _with_range(span, span.time_range.start_seconds, end_seconds)


def _with_range(span: LabeledSpan, start_seconds: float, end_seconds: float) -> LabeledSpan:
    return replace(span, time_range=TimeRange(start_seconds, end_seconds))
