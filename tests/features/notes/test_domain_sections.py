# @covers analysis:CON-022
import pytest

from konspekt.features.notes.domain.notes import BlockKind, NoteBlock, NoteSection, Notes
from konspekt.shared.timecode import TimeRange


def a_section(section_id: str, subsections: tuple[NoteSection, ...] = ()) -> NoteSection:
    return NoteSection(
        section_id=section_id,
        title=section_id,
        source_spans=(TimeRange(0.0, 1.0),),
        blocks=(NoteBlock(kind=BlockKind.PROSE, text="t"),),
        subsections=subsections,
    )


def test_two_level_nesting_is_allowed() -> None:
    notes = Notes(
        title="t", language="ru",
        sections=(a_section("s1", subsections=(a_section("s1.1"), a_section("s1.2"))),),
    )

    assert [s.section_id for s in notes.all_sections()] == ["s1", "s1.1", "s1.2"]


def test_third_nesting_level_is_rejected() -> None:
    with pytest.raises(ValueError, match="maximum depth"):
        a_section("s1", subsections=(a_section("s1.1", subsections=(a_section("s1.1.1"),)),))


def test_duplicate_ids_across_the_tree_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        Notes(
            title="t", language="ru",
            sections=(a_section("s1", subsections=(a_section("s1"),)),),
        )


def test_owning_top_section_resolves_subsection_to_parent() -> None:
    notes = Notes(
        title="t", language="ru",
        sections=(a_section("s1", subsections=(a_section("s1.1"),)), a_section("s2")),
    )

    assert notes.owning_top_section_id("s1.1") == "s1"
    assert notes.owning_top_section_id("s2") == "s2"
    assert notes.owning_top_section_id("s9") is None
