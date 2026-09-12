from dataclasses import dataclass
from enum import StrEnum

from konspekt.shared.timecode import TimeRange


class SpanLabel(StrEnum):
    CORE = "core"
    TANGENT = "tangent"
    ANECDOTE = "anecdote"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class SectionPlanEntry:
    section_id: str
    title: str
    time_range: TimeRange
    subsections: tuple["SectionPlanEntry", ...] = ()

    def __post_init__(self) -> None:
        if any(subsection.subsections for subsection in self.subsections):
            raise ValueError("plan subsections must not nest further (maximum depth is 2)")


@dataclass(frozen=True, slots=True)
class LabeledSpan:
    time_range: TimeRange
    label: SpanLabel
    section_id: str | None
    reason: str | None

    def __post_init__(self) -> None:
        if self.label is not SpanLabel.CORE and self.reason is None:
            raise ValueError("non-core span requires a reason (cut log entry)")


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    lecture_title: str
    sections_plan: tuple[SectionPlanEntry, ...]
    spans: tuple[LabeledSpan, ...]

    def all_plan_entries(self) -> tuple[SectionPlanEntry, ...]:
        flattened: list[SectionPlanEntry] = []
        for entry in self.sections_plan:
            flattened.append(entry)
            flattened.extend(entry.subsections)
        return tuple(flattened)
