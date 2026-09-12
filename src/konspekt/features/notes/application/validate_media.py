from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from konspekt.features.notes.domain.notes import (
    GENERATED_SOURCE_PREFIX,
    VIDEO_SOURCE_PREFIX,
    BlockKind,
    NoteBlock,
    NoteSection,
)
from konspekt.features.visual.domain.frame import Frame

FRAME_TIMESTAMP_TOLERANCE_SECONDS = 2.0

_HTTPS_PREFIX = "https://"


class MediaViolationKind(StrEnum):
    MISPLACED_FRAME = "misplaced_frame"
    INVALID_SOURCE_REF = "invalid_source_ref"


@dataclass(frozen=True, slots=True)
class MediaViolation:
    kind: MediaViolationKind
    section_id: str
    block: NoteBlock
    message: str


def validate_section_media(section: NoteSection, frames: Sequence[Frame]) -> list[str]:
    return [violation.message for violation in section_media_violations(section, frames)]


def section_media_violations(
    section: NoteSection, frames: Sequence[Frame]
) -> list[MediaViolation]:
    violations: list[MediaViolation] = []
    for block in section.blocks:
        if block.kind is not BlockKind.FIGURE or block.source_ref is None:
            continue
        if block.source_ref.startswith(VIDEO_SOURCE_PREFIX):
            violations.extend(
                MediaViolation(
                    kind=MediaViolationKind.MISPLACED_FRAME,
                    section_id=section.section_id,
                    block=block,
                    message=message,
                )
                for message in _frame_ref_errors(section, block.source_ref, frames)
            )
        elif not block.source_ref.startswith((_HTTPS_PREFIX, GENERATED_SOURCE_PREFIX)):
            violations.append(
                MediaViolation(
                    kind=MediaViolationKind.INVALID_SOURCE_REF,
                    section_id=section.section_id,
                    block=block,
                    message=(
                        f"figure source_ref {block.source_ref!r} in section "
                        f"{section.section_id!r} is neither a video timestamp, an HTTPS "
                        "URL nor a generated-image reference"
                    ),
                )
            )
    return violations


def _frame_ref_errors(
    section: NoteSection, source_ref: str, frames: Sequence[Frame]
) -> list[str]:
    label = source_ref.removeprefix(VIDEO_SOURCE_PREFIX)
    try:
        moment_seconds = _seconds_from_label(label)
    except ValueError:
        return [
            f"figure source_ref {source_ref!r} in section {section.section_id!r} "
            "is not a valid video HH:MM:SS timestamp"
        ]
    errors: list[str] = []
    if not any(
        span.start_seconds - FRAME_TIMESTAMP_TOLERANCE_SECONDS
        <= moment_seconds
        <= span.end_seconds + FRAME_TIMESTAMP_TOLERANCE_SECONDS
        for span in section.source_spans
    ):
        errors.append(
            f"figure timestamp {label} in section {section.section_id!r} "
            "lies outside the section source spans"
        )
    if not any(
        abs(frame.timestamp_seconds - moment_seconds) <= FRAME_TIMESTAMP_TOLERANCE_SECONDS
        for frame in frames
    ):
        errors.append(
            f"figure timestamp {label} in section {section.section_id!r} "
            "does not match any extracted frame"
        )
    return errors


def _seconds_from_label(label: str) -> float:
    hours, minutes, seconds = (int(part) for part in label.split(":"))
    return float(hours * 3600 + minutes * 60 + seconds)
