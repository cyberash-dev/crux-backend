# @covers analysis:REQ-024
# @covers analysis:DLT-028
from pathlib import Path

import pytest

from konspekt.features.notes.application.validate_media import validate_section_media
from konspekt.features.notes.domain.notes import (
    BlockKind,
    FigureProvenance,
    NoteBlock,
    NoteSection,
)
from konspekt.features.visual.domain.frame import Frame
from konspekt.shared.timecode import TimeRange


def a_section_with_figure(
    source_ref: str, provenance: FigureProvenance | None = None
) -> NoteSection:
    return NoteSection(
        section_id="s1",
        title="Первое начало",
        source_spans=(TimeRange(0.0, 60.0),),
        blocks=(
            NoteBlock(
                kind=BlockKind.FIGURE,
                image_path="frames/frame.png",
                source_ref=source_ref,
                provenance=provenance,
            ),
        ),
    )


def a_frame(timestamp_seconds: float) -> Frame:
    return Frame(
        timestamp_seconds=timestamp_seconds,
        image_path=Path("frames/frame.png"),
        dhash="0" * 16,
        ocr_text=None,
    )


def test_frame_figure_inside_span_is_valid() -> None:
    section = a_section_with_figure("video 00:00:30")

    errors = validate_section_media(section, [a_frame(30.0)])

    assert errors == []


def test_frame_figure_outside_span_is_rejected() -> None:
    section = a_section_with_figure("video 00:05:00")

    errors = validate_section_media(section, [a_frame(300.0)])

    assert len(errors) == 1
    assert "s1" in errors[0]
    assert "00:05:00" in errors[0]


def test_frame_figure_within_tolerance_past_span_end_is_valid() -> None:
    section = a_section_with_figure("video 00:01:01")

    errors = validate_section_media(section, [a_frame(61.0)])

    assert errors == []


def test_frame_figure_without_matching_frame_is_rejected() -> None:
    section = a_section_with_figure("video 00:00:30")

    errors = validate_section_media(section, [a_frame(300.0)])

    assert len(errors) == 1
    assert "frame" in errors[0]


def test_https_url_figure_is_valid() -> None:
    section = a_section_with_figure("https://example.com/diagram.png")

    errors = validate_section_media(section, [])

    assert errors == []


def test_generated_figure_is_valid_without_frames() -> None:
    section = a_section_with_figure("generated:codex")

    errors = validate_section_media(section, [])

    assert errors == []


def test_plain_http_url_figure_is_rejected() -> None:
    section = a_section_with_figure(
        "http://example.com/diagram.png", provenance=FigureProvenance.COMMONS
    )

    errors = validate_section_media(section, [])

    assert len(errors) == 1
    assert "http://example.com/diagram.png" in errors[0]


def test_malformed_video_label_is_rejected() -> None:
    section = a_section_with_figure("video thirty seconds in")

    errors = validate_section_media(section, [a_frame(30.0)])

    assert len(errors) == 1
    assert "video thirty seconds in" in errors[0]


def test_prose_blocks_are_not_checked() -> None:
    section = NoteSection(
        section_id="s1",
        title="Первое начало",
        source_spans=(TimeRange(0.0, 60.0),),
        blocks=(NoteBlock(kind=BlockKind.PROSE, text="Энергия сохраняется."),),
    )

    errors = validate_section_media(section, [])

    assert errors == []
