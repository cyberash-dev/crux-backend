# @covers analysis:REQ-020
import pytest

from konspekt.features.segmentation.application.segment_lecture import (
    EmptyTranscriptError,
    segment_lecture,
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


class RecordedSegmentationLlm:
    def __init__(
        self,
        sections_plan: list[SectionPlanEntry],
        labeled_spans: list[LabeledSpan],
        lecture_title: str = "Математический анализ",
    ) -> None:
        self._sections_plan = sections_plan
        self._labeled_spans = labeled_spans
        self._lecture_title = lecture_title

    def plan_outline(
        self, transcript: Transcript
    ) -> tuple[str, list[SectionPlanEntry]]:
        return (self._lecture_title, self._sections_plan)

    def label_spans(
        self, transcript: Transcript, sections_plan: list[SectionPlanEntry]
    ) -> list[LabeledSpan]:
        return self._labeled_spans


def a_lecture_transcript() -> Transcript:
    return Transcript(
        language="ru",
        segments=(
            TranscriptSegment(TimeRange(0.0, 60.0), "intro words", None),
            TranscriptSegment(TimeRange(60.0, 120.0), "core content", None),
        ),
    )


def a_section_plan() -> list[SectionPlanEntry]:
    return [SectionPlanEntry("s1", "Introduction", TimeRange(0.0, 120.0))]


def test_full_coverage_labeling_produces_segmentation_result() -> None:
    spans = [
        LabeledSpan(TimeRange(0.0, 60.0), SpanLabel.ADMIN, None, "course logistics"),
        LabeledSpan(TimeRange(60.0, 120.0), SpanLabel.CORE, "s1", None),
    ]
    llm = RecordedSegmentationLlm(a_section_plan(), spans)

    result = segment_lecture(a_lecture_transcript(), llm)

    assert result.sections_plan == tuple(a_section_plan())
    assert result.spans == tuple(spans)


def test_every_stored_span_carries_one_valid_label() -> None:
    spans = [
        LabeledSpan(TimeRange(0.0, 60.0), SpanLabel.TANGENT, None, "off topic"),
        LabeledSpan(TimeRange(60.0, 120.0), SpanLabel.CORE, "s1", None),
    ]
    llm = RecordedSegmentationLlm(a_section_plan(), spans)

    result = segment_lecture(a_lecture_transcript(), llm)

    assert all(span.label in SpanLabel for span in result.spans)


def test_gap_with_speech_in_returned_spans_is_closed_and_the_timeline_stays_covered() -> None:
    transcript_with_speech_in_gap = Transcript(
        language="ru",
        segments=(
            TranscriptSegment(TimeRange(0.0, 50.0), "intro words", None),
            TranscriptSegment(TimeRange(50.0, 60.0), "lost words", None),
            TranscriptSegment(TimeRange(60.0, 120.0), "core content", None),
        ),
    )
    spans_with_gap = [
        LabeledSpan(TimeRange(0.0, 50.0), SpanLabel.CORE, "s1", None),
        LabeledSpan(TimeRange(60.0, 120.0), SpanLabel.CORE, "s1", None),
    ]
    llm = RecordedSegmentationLlm(a_section_plan(), spans_with_gap)

    result = segment_lecture(transcript_with_speech_in_gap, llm)

    assert [span.time_range for span in result.spans] == [
        TimeRange(0.0, 60.0),
        TimeRange(60.0, 120.0),
    ]


def test_lecture_title_from_outline_is_stored_on_result() -> None:
    spans = [LabeledSpan(TimeRange(0.0, 120.0), SpanLabel.CORE, "s1", None)]
    llm = RecordedSegmentationLlm(
        a_section_plan(), spans, lecture_title="Пределы и производные"
    )

    result = segment_lecture(a_lecture_transcript(), llm)

    assert result.lecture_title == "Пределы и производные"


def test_empty_transcript_raises_typed_error() -> None:
    empty_transcript = Transcript(language="ru", segments=())
    llm = RecordedSegmentationLlm(a_section_plan(), [])

    with pytest.raises(EmptyTranscriptError, match="no segments"):
        segment_lecture(empty_transcript, llm)


def test_llm_boundary_drift_within_snap_tolerance_is_accepted() -> None:
    transcript = Transcript(
        language="ru",
        segments=(
            TranscriptSegment(TimeRange(0.0, 400.0), "Первая часть.", None),
            TranscriptSegment(TimeRange(400.0, 720.1), "Вторая часть.", None),
        ),
    )
    drifting_llm = RecordedSegmentationLlm(
        sections_plan=[SectionPlanEntry("s1", "Тема", TimeRange(0.0, 720.1))],
        labeled_spans=[
            LabeledSpan(TimeRange(1.2, 400.0), SpanLabel.CORE, "s1", None),
            LabeledSpan(TimeRange(400.0, 719.0), SpanLabel.CORE, "s1", None),
        ],
    )

    result = segment_lecture(transcript, drifting_llm)

    assert result.spans[0].time_range.start_seconds == 0.0
    assert result.spans[-1].time_range.end_seconds == 720.1
