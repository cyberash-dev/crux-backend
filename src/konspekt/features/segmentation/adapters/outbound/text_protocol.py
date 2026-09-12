from collections.abc import Mapping, Sequence
from typing import Any

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

WINDOW_SECONDS: float = 1800.0
MAX_PLAN_DEPTH: int = 2


class SegmentationResponseFormatError(Exception):
    pass


def plan_outline_prompt(transcript: Transcript) -> str:
    return (
        "You are structuring a lecture transcript into a hierarchical outline.\n"
        "Read the full transcript and return the lecture_title (a concise\n"
        "subject-matter title of the lecture itself, not a meta description)\n"
        "and an ordered list of sections covering the whole lecture.\n"
        "Group related topics together: aim for 5-10 top-level sections and\n"
        "never more than 12. A top-level section may carry subsections with\n"
        'dotted ids (like "s2.1") whose time ranges lie inside the parent\n'
        "range; subsections themselves stay flat. A short lecture (under 20\n"
        "minutes) may keep a flat plan without subsections.\n"
        'For every entry give a short stable section_id (like "s1"), a\n'
        "concise title, and its start_seconds and end_seconds boundaries\n"
        "taken from the timecodes below.\n\n"
        f"Transcript:\n{_transcript_lines(transcript.segments)}"
    )


def label_spans_prompt(
    window: Sequence[TranscriptSegment], sections_plan: Sequence[SectionPlanEntry]
) -> str:
    window_range = TimeRange(
        window[0].time_range.start_seconds, window[-1].time_range.end_seconds
    )
    return (
        "You are labeling every moment of a lecture transcript window.\n"
        f"Split the window [{window_range.start_label()} - {window_range.end_label()}]"
        " into contiguous spans covering it without gaps or overlaps.\n"
        "Give every span exactly one label: core, tangent, anecdote, admin.\n"
        "Be conservative: if you are unsure, label the span core.\n"
        "A core span carries the section_id of the most specific matching\n"
        "plan entry: a subsection id when the section has subsections,\n"
        "otherwise the top-level id. It also carries a null reason. Every\n"
        "non-core span carries a null section_id and a one-sentence reason\n"
        "explaining the cut.\n\n"
        f"Section plan of the whole lecture:\n{_section_plan_lines(sections_plan)}\n\n"
        f"Window transcript:\n{_transcript_lines(window)}"
    )


def parse_plan_outline(
    payload: Mapping[str, Any],
) -> tuple[str, list[SectionPlanEntry]]:
    if "lecture_title" not in payload:
        raise SegmentationResponseFormatError("outline payload has no lecture_title")
    try:
        entries = [
            _parse_plan_entry(raw_section, depth=1)
            for raw_section in payload["sections"]
        ]
    except (KeyError, TypeError) as error:
        raise SegmentationResponseFormatError(
            f"sections plan payload mismatch: {error!r}"
        ) from error
    _ensure_unique_plan_ids(entries)
    return (payload["lecture_title"], entries)


def _ensure_unique_plan_ids(entries: Sequence[SectionPlanEntry]) -> None:
    seen_ids: set[str] = set()
    for entry in entries:
        for plan_id in (
            entry.section_id,
            *(subsection.section_id for subsection in entry.subsections),
        ):
            if plan_id in seen_ids:
                raise SegmentationResponseFormatError(
                    f"duplicate plan section_id {plan_id!r}"
                )
            seen_ids.add(plan_id)


def _parse_plan_entry(raw_entry: Mapping[str, Any], depth: int) -> SectionPlanEntry:
    raw_subsections = raw_entry.get("subsections", [])
    if raw_subsections and depth >= MAX_PLAN_DEPTH:
        raise SegmentationResponseFormatError(
            f"plan entry {raw_entry['section_id']!r} exceeds the maximum "
            f"nesting depth of {MAX_PLAN_DEPTH}"
        )
    return SectionPlanEntry(
        section_id=raw_entry["section_id"],
        title=raw_entry["title"],
        time_range=TimeRange(raw_entry["start_seconds"], raw_entry["end_seconds"]),
        subsections=tuple(
            _parse_plan_entry(raw_subsection, depth=depth + 1)
            for raw_subsection in raw_subsections
        ),
    )


def parse_labeled_spans(payload: Mapping[str, Any]) -> list[LabeledSpan]:
    try:
        return [_parse_labeled_span(raw_span) for raw_span in payload["spans"]]
    except (KeyError, TypeError) as error:
        raise SegmentationResponseFormatError(
            f"spans payload mismatch: {error!r}"
        ) from error


def transcript_windows(
    transcript: Transcript, window_seconds: float = WINDOW_SECONDS
) -> list[tuple[TranscriptSegment, ...]]:
    if not transcript.segments:
        return []
    windows: list[tuple[TranscriptSegment, ...]] = []
    current: list[TranscriptSegment] = []
    window_start_seconds = transcript.segments[0].time_range.start_seconds
    for segment in transcript.segments:
        starts_past_window = (
            segment.time_range.start_seconds >= window_start_seconds + window_seconds
        )
        if starts_past_window and current:
            windows.append(tuple(current))
            current = []
            window_start_seconds = segment.time_range.start_seconds
        current.append(segment)
    windows.append(tuple(current))
    return windows


def merge_span_windows(
    windows: Sequence[Sequence[LabeledSpan]],
) -> list[LabeledSpan]:
    flattened = [span for window in windows for span in window]
    return sorted(flattened, key=lambda span: span.time_range.start_seconds)


def _parse_labeled_span(raw_span: Mapping[str, Any]) -> LabeledSpan:
    try:
        label = SpanLabel(raw_span["label"])
    except ValueError as error:
        raise SegmentationResponseFormatError(
            f"unknown span label {raw_span['label']!r}"
        ) from error
    if label is not SpanLabel.CORE and raw_span["reason"] is None:
        raise SegmentationResponseFormatError(
            f"non-core span at {raw_span['start_seconds']}s has null reason"
        )
    return LabeledSpan(
        time_range=TimeRange(raw_span["start_seconds"], raw_span["end_seconds"]),
        label=label,
        section_id=raw_span["section_id"],
        reason=raw_span["reason"],
    )


def _transcript_lines(segments: Sequence[TranscriptSegment]) -> str:
    return "\n".join(
        f"[{segment.time_range.start_label()}] {segment.text}" for segment in segments
    )


def _section_plan_lines(sections_plan: Sequence[SectionPlanEntry]) -> str:
    lines: list[str] = []
    for entry in sections_plan:
        lines.append(_plan_entry_line(entry, indent=""))
        lines.extend(
            _plan_entry_line(subsection, indent="  ")
            for subsection in entry.subsections
        )
    return "\n".join(lines)


def _plan_entry_line(entry: SectionPlanEntry, indent: str) -> str:
    return (
        f"{indent}{entry.section_id} | {entry.title} | "
        f"{entry.time_range.start_seconds}-{entry.time_range.end_seconds}"
    )
