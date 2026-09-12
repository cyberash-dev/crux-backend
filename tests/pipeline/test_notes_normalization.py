# @covers analysis:REQ-024
from pathlib import Path

from konspekt.features.notes.domain.notes import BlockKind, NoteBlock, NoteSection, Notes
from konspekt.features.visual.domain.frame import Frame
from konspekt.pipeline.notes_enrichment import normalize_figure_paths
from konspekt.shared.timecode import TimeRange


def notes_with_figure(image_path: str) -> Notes:
    return Notes(
        title="t",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="s",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=(
                    NoteBlock(
                        kind=BlockKind.FIGURE,
                        image_path=image_path,
                        caption="c",
                        source_ref="video 00:00:30",
                    ),
                ),
            ),
        ),
    )


KNOWN_FRAMES = [Frame(30.0, Path("frames/frame_30000.jpg"), "a" * 16, None)]


def test_model_echoed_cwd_relative_path_is_replaced_by_frame_path() -> None:
    notes = notes_with_figure("out/lecture/work/frames/frame_30000.jpg")

    normalized = normalize_figure_paths(notes, KNOWN_FRAMES)

    assert normalized.sections[0].blocks[0].image_path == "frames/frame_30000.jpg"


def test_absolute_path_is_replaced_by_frame_path() -> None:
    notes = notes_with_figure("/abs/work/frames/frame_30000.jpg")

    normalized = normalize_figure_paths(notes, KNOWN_FRAMES)

    assert normalized.sections[0].blocks[0].image_path == "frames/frame_30000.jpg"


def test_already_relative_frame_path_is_idempotent() -> None:
    notes = notes_with_figure("frames/frame_30000.jpg")

    normalized = normalize_figure_paths(notes, KNOWN_FRAMES)

    assert normalized.sections[0].blocks[0].image_path == "frames/frame_30000.jpg"


def test_unknown_basename_is_left_untouched() -> None:
    notes = notes_with_figure("images/external-diagram.png")

    normalized = normalize_figure_paths(notes, KNOWN_FRAMES)

    assert normalized.sections[0].blocks[0].image_path == "images/external-diagram.png"


def test_relative_frames_strip_work_dir_prefix_in_any_form() -> None:
    from konspekt.pipeline.orchestrator import _relative_frames

    work_dir = Path("out/lecture/work")
    frames = [
        Frame(1.0, Path("out/lecture/work/frames/frame_1.jpg"), "a" * 16, None),
        Frame(2.0, (Path.cwd() / "out/lecture/work/frames/frame_2.jpg"), "b" * 16, None),
        Frame(3.0, Path("frames/frame_3.jpg"), "c" * 16, None),
    ]

    relative = _relative_frames(frames, work_dir)

    assert [str(frame.image_path) for frame in relative] == [
        "frames/frame_1.jpg",
        "frames/frame_2.jpg",
        "frames/frame_3.jpg",
    ]


def test_figure_paths_inside_subsections_are_normalized() -> None:
    parent = NoteSection(
        section_id="s1",
        title="s",
        source_spans=(TimeRange(0.0, 60.0),),
        blocks=(),
        subsections=(
            NoteSection(
                section_id="s1.1",
                title="sub",
                source_spans=(TimeRange(0.0, 30.0),),
                blocks=(
                    NoteBlock(
                        kind=BlockKind.FIGURE,
                        image_path="out/lecture/work/frames/frame_30000.jpg",
                        source_ref="video 00:00:30",
                    ),
                ),
            ),
        ),
    )
    notes = Notes(title="t", language="ru", sections=(parent,))

    normalized = normalize_figure_paths(notes, KNOWN_FRAMES)

    block = normalized.sections[0].subsections[0].blocks[0]
    assert block.image_path == "frames/frame_30000.jpg"


# @covers analysis:REQ-027
def test_repeated_external_figure_is_kept_only_at_its_first_occurrence() -> None:
    from konspekt.pipeline.notes_enrichment import without_duplicate_external_figures

    def external_figure() -> NoteBlock:
        return NoteBlock(
            kind=BlockKind.FIGURE,
            image_path="images/humerus.jpg",
            source_ref="https://commons.wikimedia.org/wiki/File:HumerusFront.JPG",
            caption="Плечевая кость",
        )

    def frame_figure() -> NoteBlock:
        return NoteBlock(
            kind=BlockKind.FIGURE,
            image_path="frames/frame_1.jpg",
            source_ref="video 00:00:01",
        )

    notes = Notes(
        title="t",
        language="ru",
        sections=(
            NoteSection(
                section_id="s3",
                title="s3",
                source_spans=(TimeRange(0.0, 10.0),),
                blocks=(external_figure(), frame_figure()),
                subsections=(
                    NoteSection(
                        section_id="s3.1",
                        title="s3.1",
                        source_spans=(TimeRange(0.0, 5.0),),
                        blocks=(external_figure(), frame_figure()),
                    ),
                ),
            ),
        ),
    )

    deduplicated = without_duplicate_external_figures(notes)

    top_blocks = deduplicated.sections[0].blocks
    sub_blocks = deduplicated.sections[0].subsections[0].blocks
    assert [block.kind for block in top_blocks] == [BlockKind.FIGURE, BlockKind.FIGURE]
    assert [block.kind for block in sub_blocks] == [BlockKind.FIGURE]
    assert sub_blocks[0].source_ref == "video 00:00:01"
