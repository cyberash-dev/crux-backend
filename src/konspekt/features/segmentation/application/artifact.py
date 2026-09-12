from collections.abc import Mapping
from typing import Any

from konspekt.features.segmentation.domain.segments import (
    LabeledSpan,
    SectionPlanEntry,
    SegmentationResult,
    SpanLabel,
)
from konspekt.shared.timecode import TimeRange

MAX_PLAN_DEPTH: int = 2


class SegmentationPayloadError(Exception):
    pass


def segmentation_payload(result: SegmentationResult) -> dict[str, Any]:
    return {
        "lecture_title": result.lecture_title,
        "sections_plan": [
            _section_entry_payload(entry) for entry in result.sections_plan
        ],
        "spans": [
            {
                "start_seconds": span.time_range.start_seconds,
                "end_seconds": span.time_range.end_seconds,
                "label": span.label.value,
                "section_id": span.section_id,
                "reason": span.reason,
            }
            for span in result.spans
        ],
    }


def parse_segmentation_payload(payload: Mapping[str, Any]) -> SegmentationResult:
    if "lecture_title" not in payload:
        raise SegmentationPayloadError("payload is missing lecture_title")
    sections_plan = tuple(
        _parse_section_entry(raw_entry, depth=1)
        for raw_entry in payload["sections_plan"]
    )
    _ensure_unique_plan_ids(sections_plan)
    return SegmentationResult(
        lecture_title=payload["lecture_title"],
        sections_plan=sections_plan,
        spans=tuple(_parse_span(raw_span) for raw_span in payload["spans"]),
    )


def _ensure_unique_plan_ids(sections_plan: tuple[SectionPlanEntry, ...]) -> None:
    seen_ids: set[str] = set()
    for entry in sections_plan:
        for plan_id in (
            entry.section_id,
            *(subsection.section_id for subsection in entry.subsections),
        ):
            if plan_id in seen_ids:
                raise SegmentationPayloadError(
                    f"duplicate plan section_id {plan_id!r}"
                )
            seen_ids.add(plan_id)


def _section_entry_payload(entry: SectionPlanEntry) -> dict[str, Any]:
    return {
        "section_id": entry.section_id,
        "title": entry.title,
        "start_seconds": entry.time_range.start_seconds,
        "end_seconds": entry.time_range.end_seconds,
        "subsections": [
            _section_entry_payload(subsection) for subsection in entry.subsections
        ],
    }


def _parse_section_entry(
    raw_entry: Mapping[str, Any], depth: int
) -> SectionPlanEntry:
    raw_subsections = raw_entry.get("subsections", [])
    if raw_subsections and depth >= MAX_PLAN_DEPTH:
        raise SegmentationPayloadError(
            f"plan entry {raw_entry['section_id']!r} exceeds the maximum "
            f"nesting depth of {MAX_PLAN_DEPTH}"
        )
    return SectionPlanEntry(
        section_id=raw_entry["section_id"],
        title=raw_entry["title"],
        time_range=TimeRange(raw_entry["start_seconds"], raw_entry["end_seconds"]),
        subsections=tuple(
            _parse_section_entry(raw_subsection, depth=depth + 1)
            for raw_subsection in raw_subsections
        ),
    )


def _parse_span(raw_span: Mapping[str, Any]) -> LabeledSpan:
    try:
        label = SpanLabel(raw_span["label"])
    except ValueError as error:
        raise SegmentationPayloadError(
            f"unknown span label {raw_span['label']!r}"
        ) from error
    if label is not SpanLabel.CORE and raw_span["reason"] is None:
        raise SegmentationPayloadError(
            f"non-core span at {raw_span['start_seconds']}s has null reason"
        )
    return LabeledSpan(
        time_range=TimeRange(raw_span["start_seconds"], raw_span["end_seconds"]),
        label=label,
        section_id=raw_span["section_id"],
        reason=raw_span["reason"],
    )
