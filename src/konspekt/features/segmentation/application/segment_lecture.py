from konspekt.features.segmentation.application.coverage import (
    validate_timeline_coverage,
)
from konspekt.features.segmentation.application.snap import snap_spans_to_timeline
from konspekt.features.segmentation.domain.segments import SegmentationResult
from konspekt.shared.timecode import TimeRange
from konspekt.features.segmentation.ports.outbound.segmentation_llm import (
    SegmentationLlmPort,
)
from konspekt.features.transcription.domain.transcript import Transcript


class EmptyTranscriptError(Exception):
    def __init__(self) -> None:
        super().__init__("transcript has no segments to label")


def segment_lecture(
    transcript: Transcript, llm: SegmentationLlmPort
) -> SegmentationResult:
    if not transcript.segments:
        raise EmptyTranscriptError
    lecture_title, sections_plan = llm.plan_outline(transcript)
    timeline = TimeRange(
        transcript.segments[0].time_range.start_seconds,
        transcript.segments[-1].time_range.end_seconds,
    )
    spans = snap_spans_to_timeline(
        llm.label_spans(transcript, sections_plan), timeline, transcript.segments
    )
    validate_timeline_coverage(spans, timeline)
    return SegmentationResult(
        lecture_title=lecture_title,
        sections_plan=tuple(sections_plan),
        spans=tuple(spans),
    )
