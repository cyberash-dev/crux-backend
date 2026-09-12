from konspekt.features.segmentation.domain.segments import (
    LabeledSpan,
    SegmentationResult,
    SpanLabel,
)
from konspekt.features.transcription.domain.transcript import (
    Transcript,
    TranscriptSegment,
)
from konspekt.shared.timecode import TimeRange


def core_text(transcript: Transcript, segmentation: SegmentationResult) -> str:
    blocks = [
        _span_block(span, transcript.segments, within=None)
        for span in segmentation.spans
        if span.label is SpanLabel.CORE
    ]
    return "\n".join(block for block in blocks if block)


def core_text_for_range(
    transcript: Transcript, segmentation: SegmentationResult, time_range: TimeRange
) -> str:
    blocks = [
        _span_block(span, transcript.segments, within=time_range)
        for span in segmentation.spans
        if span.label is SpanLabel.CORE
        and _is_overlapping(span.time_range, time_range)
    ]
    return "\n".join(block for block in blocks if block)


def _span_block(
    span: LabeledSpan,
    segments: tuple[TranscriptSegment, ...],
    within: TimeRange | None,
) -> str:
    texts = [
        segment.text
        for segment in segments
        if _is_segment_inside_span(segment, span)
        and (within is None or _is_midpoint_inside(segment, within))
    ]
    if not texts:
        return ""
    block_start_seconds = span.time_range.start_seconds
    if within is not None:
        block_start_seconds = max(block_start_seconds, within.start_seconds)
    label = TimeRange(block_start_seconds, span.time_range.end_seconds).start_label()
    return f"[{label}] {' '.join(texts)}"


def _is_segment_inside_span(segment: TranscriptSegment, span: LabeledSpan) -> bool:
    return _is_midpoint_inside(segment, span.time_range)


def _is_midpoint_inside(segment: TranscriptSegment, time_range: TimeRange) -> bool:
    midpoint_seconds = (
        segment.time_range.start_seconds + segment.time_range.end_seconds
    ) / 2
    return time_range.start_seconds <= midpoint_seconds < time_range.end_seconds


def _is_overlapping(left: TimeRange, right: TimeRange) -> bool:
    return (
        left.start_seconds < right.end_seconds
        and right.start_seconds < left.end_seconds
    )
