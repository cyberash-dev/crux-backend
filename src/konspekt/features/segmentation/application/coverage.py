from collections.abc import Sequence

from konspekt.features.segmentation.domain.segments import LabeledSpan
from konspekt.shared.timecode import TimeRange

COVERAGE_TOLERANCE_SECONDS: float = 0.5


class TimelineCoverageError(Exception):
    def __init__(self, position_seconds: float, detail: str) -> None:
        super().__init__(f"{detail} at {position_seconds:.1f}s")
        self.position_seconds = position_seconds


def validate_timeline_coverage(
    spans: Sequence[LabeledSpan], timeline: TimeRange
) -> None:
    if not spans:
        raise TimelineCoverageError(timeline.start_seconds, "no spans cover the timeline")
    ordered = sorted(spans, key=lambda span: span.time_range.start_seconds)
    first_start = ordered[0].time_range.start_seconds
    if abs(first_start - timeline.start_seconds) > COVERAGE_TOLERANCE_SECONDS:
        raise TimelineCoverageError(timeline.start_seconds, "gap before first span")
    for previous, current in zip(ordered, ordered[1:], strict=False):
        joint_seconds = current.time_range.start_seconds - previous.time_range.end_seconds
        if joint_seconds > COVERAGE_TOLERANCE_SECONDS:
            raise TimelineCoverageError(
                previous.time_range.end_seconds, "gap between spans"
            )
        if joint_seconds < -COVERAGE_TOLERANCE_SECONDS:
            raise TimelineCoverageError(
                current.time_range.start_seconds, "overlapping spans"
            )
    last_end = ordered[-1].time_range.end_seconds
    if abs(last_end - timeline.end_seconds) > COVERAGE_TOLERANCE_SECONDS:
        raise TimelineCoverageError(last_end, "gap after last span")
