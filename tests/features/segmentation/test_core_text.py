from konspekt.features.segmentation.application.core_text import (
    core_text,
    core_text_for_range,
)
from konspekt.features.segmentation.domain.segments import (
    LabeledSpan,
    SectionPlanEntry,
    SegmentationResult,
    SpanLabel,
)
from konspekt.features.transcription.domain.transcript import (
    Transcript,
    TranscriptSegment,
)
from konspekt.shared.timecode import TimeRange


def a_transcript_with_tangent_in_the_middle() -> Transcript:
    return Transcript(
        language="ru",
        segments=(
            TranscriptSegment(TimeRange(0.0, 60.0), "derivative definition", None),
            TranscriptSegment(TimeRange(60.0, 120.0), "funny cat story", None),
            TranscriptSegment(TimeRange(120.0, 3725.0), "chain rule proof", None),
        ),
    )


def a_segmentation_with_tangent_in_the_middle() -> SegmentationResult:
    return SegmentationResult(
        lecture_title="Derivatives",
        sections_plan=(SectionPlanEntry("s1", "Derivatives", TimeRange(0.0, 3725.0)),),
        spans=(
            LabeledSpan(TimeRange(0.0, 60.0), SpanLabel.CORE, "s1", None),
            LabeledSpan(TimeRange(60.0, 120.0), SpanLabel.TANGENT, None, "cat story"),
            LabeledSpan(TimeRange(120.0, 3725.0), SpanLabel.CORE, "s1", None),
        ),
    )


# @covers analysis:REQ-020
def test_non_core_span_text_is_absent_from_core_text() -> None:
    transcript = a_transcript_with_tangent_in_the_middle()
    segmentation = a_segmentation_with_tangent_in_the_middle()

    text = core_text(transcript, segmentation)

    assert "funny cat story" not in text
    assert "derivative definition" in text
    assert "chain rule proof" in text


def test_core_spans_are_prefixed_with_hh_mm_ss_timecodes() -> None:
    transcript = a_transcript_with_tangent_in_the_middle()
    segmentation = a_segmentation_with_tangent_in_the_middle()

    text = core_text(transcript, segmentation)

    assert "[00:00:00]" in text
    assert "[00:02:00]" in text


def test_timecode_covers_hours_past_the_first() -> None:
    transcript = Transcript(
        language="ru",
        segments=(TranscriptSegment(TimeRange(3661.0, 3700.0), "late remark", None),),
    )
    segmentation = SegmentationResult(
        lecture_title="Late",
        sections_plan=(SectionPlanEntry("s1", "Late", TimeRange(3661.0, 3700.0)),),
        spans=(LabeledSpan(TimeRange(3661.0, 3700.0), SpanLabel.CORE, "s1", None),),
    )

    text = core_text(transcript, segmentation)

    assert "[01:01:01]" in text


def test_range_selection_excludes_core_text_outside_the_range() -> None:
    transcript = a_transcript_with_tangent_in_the_middle()
    segmentation = a_segmentation_with_tangent_in_the_middle()

    text = core_text_for_range(transcript, segmentation, TimeRange(120.0, 3725.0))

    assert "chain rule proof" in text
    assert "derivative definition" not in text


def test_range_selection_excludes_tangent_inside_the_range() -> None:
    transcript = a_transcript_with_tangent_in_the_middle()
    segmentation = a_segmentation_with_tangent_in_the_middle()

    text = core_text_for_range(transcript, segmentation, TimeRange(0.0, 3725.0))

    assert "funny cat story" not in text
    assert "derivative definition" in text
