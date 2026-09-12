from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from konspekt.features.factcheck.domain.claims import CheckedClaim
from konspekt.features.notes.domain.notes import (
    BlockKind,
    FigureProvenance,
    NoteBlock,
    Notes,
    NoteSection,
)
from konspekt.features.visual.domain.frame import Frame


def with_factcheck_sources(notes: Notes, claims: Sequence[CheckedClaim]) -> Notes:
    """output:CON-030 requires factcheck annotations to carry their source URLs;
    the notes port only guarantees claim_ref, so the missing URL is appended here."""
    return replace(
        notes,
        sections=tuple(_enriched_section(section, claims) for section in notes.sections),
    )


def _enriched_section(section: NoteSection, claims: Sequence[CheckedClaim]) -> NoteSection:
    return replace(
        section,
        blocks=tuple(_enriched_block(block, claims) for block in section.blocks),
        subsections=tuple(
            _enriched_section(subsection, claims) for subsection in section.subsections
        ),
    )


def _enriched_block(block: NoteBlock, claims: Sequence[CheckedClaim]) -> NoteBlock:
    if block.kind is not BlockKind.FACTCHECK_NOTE or block.claim_ref is None:
        return block
    claim = claims[block.claim_ref]
    if not claim.sources or block.text is None or claim.sources[0] in block.text:
        return block
    return replace(block, text=f"{block.text} ({claim.sources[0]})")


def normalize_figure_paths(notes: Notes, frames: Sequence[Frame]) -> Notes:
    """The notes model echoes frame paths as it saw them (absolute or
    cwd-relative); artifacts store work-dir-relative paths (CON-022), so
    figure paths are mapped back to the known frame by basename."""
    frame_paths_by_name = {frame.image_path.name: str(frame.image_path) for frame in frames}
    return replace(
        notes,
        sections=tuple(
            _normalized_section(section, frame_paths_by_name) for section in notes.sections
        ),
    )


def _normalized_section(
    section: NoteSection, frame_paths_by_name: dict[str, str]
) -> NoteSection:
    return replace(
        section,
        blocks=tuple(
            _normalized_block(block, frame_paths_by_name) for block in section.blocks
        ),
        subsections=tuple(
            _normalized_section(subsection, frame_paths_by_name)
            for subsection in section.subsections
        ),
    )


def _normalized_block(block: NoteBlock, frame_paths_by_name: dict[str, str]) -> NoteBlock:
    if block.kind is not BlockKind.FIGURE or block.image_path is None:
        return block
    known_path = frame_paths_by_name.get(Path(block.image_path).name)
    if known_path is None or block.image_path == known_path:
        return block
    return replace(block, image_path=known_path)


def with_work_dir_relative_figures(notes: Notes, work_dir: Path) -> Notes:
    """Resolved illustrations are stored under the work directory with
    absolute paths; artifacts keep work-dir-relative paths (CON-022)."""
    return replace(
        notes,
        sections=tuple(_relativized_section(section, work_dir) for section in notes.sections),
    )


def _relativized_section(section: NoteSection, work_dir: Path) -> NoteSection:
    return replace(
        section,
        blocks=tuple(_relativized_block(block, work_dir) for block in section.blocks),
        subsections=tuple(
            _relativized_section(subsection, work_dir) for subsection in section.subsections
        ),
    )


def _relativized_block(block: NoteBlock, work_dir: Path) -> NoteBlock:
    if block.kind is not BlockKind.FIGURE or block.image_path is None:
        return block
    image_path = Path(block.image_path)
    for base in (work_dir, work_dir.resolve()):
        if image_path.is_relative_to(base):
            return replace(block, image_path=str(image_path.relative_to(base)))
    return block


def without_duplicate_external_figures(notes: Notes) -> Notes:
    """Independent per-section composition can pick the same Commons or
    generated image for a parent and its subsection; only the first
    occurrence in outline order stays."""
    seen_source_refs: set[str] = set()
    return replace(
        notes,
        sections=tuple(
            _section_without_duplicate_figures(section, seen_source_refs)
            for section in notes.sections
        ),
    )


def _section_without_duplicate_figures(
    section: NoteSection, seen_source_refs: set[str]
) -> NoteSection:
    kept_blocks: list[NoteBlock] = []
    for block in section.blocks:
        if (
            block.kind is BlockKind.FIGURE
            and block.provenance is not FigureProvenance.VIDEO_FRAME
            and block.source_ref is not None
        ):
            if block.source_ref in seen_source_refs:
                continue
            seen_source_refs.add(block.source_ref)
        kept_blocks.append(block)
    return replace(
        section,
        blocks=tuple(kept_blocks),
        subsections=tuple(
            _section_without_duplicate_figures(subsection, seen_source_refs)
            for subsection in section.subsections
        ),
    )
