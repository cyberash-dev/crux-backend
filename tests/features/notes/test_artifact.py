# @covers analysis:CON-022
# @covers analysis:DLT-020
# @covers analysis:DLT-022
# @covers analysis:DLT-027
# @covers analysis:DLT-031
import pytest

from konspekt.features.notes.application.artifact import (
    NotesArtifactError,
    notes_payload,
    parse_block_payload,
    parse_notes_payload,
)
from konspekt.features.notes.domain.notes import (
    BlockKind,
    BlockOrigin,
    ChartData,
    ChartKind,
    ChartSeries,
    DiagramData,
    DiagramEdge,
    DiagramKind,
    DiagramNode,
    FigureProvenance,
    NoteBlock,
    NoteSection,
    Notes,
    TableData,
)
from konspekt.shared.timecode import TimeRange


def a_notes() -> Notes:
    return Notes(
        title="Введение в термодинамику",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Первое начало",
                source_spans=(TimeRange(0.0, 120.0), TimeRange(300.0, 360.0)),
                blocks=(
                    NoteBlock(kind=BlockKind.PROSE, text="**Энергия** сохраняется."),
                    NoteBlock(
                        kind=BlockKind.DEFINITION,
                        term="Внутренняя энергия",
                        text="Сумма кинетической и потенциальной энергии частиц системы.",
                    ),
                    NoteBlock(
                        kind=BlockKind.FACT,
                        text="Джоуль измерял механический эквивалент теплоты на пивоварне.",
                    ),
                    NoteBlock(
                        kind=BlockKind.FIGURE,
                        image_path="frames/frame_30.png",
                        caption="Схема цикла",
                        source_ref="video 00:00:30",
                    ),
                    NoteBlock(
                        kind=BlockKind.FACTCHECK_NOTE,
                        text="Лектор утверждает X, источники расходятся.",
                        claim_ref=0,
                    ),
                ),
                subsections=(
                    NoteSection(
                        section_id="s1.1",
                        title="Работа и теплота",
                        source_spans=(TimeRange(30.0, 60.0),),
                        blocks=(NoteBlock(kind=BlockKind.PROSE, text="Работа и теплота."),),
                    ),
                ),
            ),
        ),
    )


def a_block_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "kind": "prose",
        "text": "Энергия сохраняется.",
        "term": None,
        "image_path": None,
        "caption": None,
        "source_ref": None,
        "claim_ref": None,
    }
    payload.update(overrides)
    return payload


def a_notes_payload(blocks: list[dict[str, object]]) -> dict[str, object]:
    return {
        "title": "Введение в термодинамику",
        "language": "ru",
        "sections": [
            {
                "section_id": "s1",
                "title": "Первое начало",
                "source_spans": [[0.0, 120.0]],
                "blocks": blocks,
            }
        ],
    }


def test_round_trip_preserves_notes() -> None:
    notes = a_notes()

    restored = parse_notes_payload(notes_payload(notes), claims_count=1)

    assert restored == notes


def test_payload_uses_contract_field_names() -> None:
    payload = notes_payload(a_notes())

    assert set(payload) == {"title", "language", "sections"}
    section = payload["sections"][0]
    assert set(section) == {"section_id", "title", "source_spans", "subsections", "blocks"}
    assert set(section["blocks"][0]) == {
        "kind",
        "text",
        "term",
        "image_path",
        "caption",
        "source_ref",
        "claim_ref",
        "provenance",
        "origin",
        "table",
        "diagram",
        "chart",
    }


def test_origin_round_trips_on_fact_and_definition_blocks() -> None:
    notes = Notes(
        title="Анатомия",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Кости",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=(
                    NoteBlock(
                        kind=BlockKind.FACT,
                        text="Лучевая кость лежит латерально.",
                        origin=BlockOrigin.LECTURE,
                    ),
                    NoteBlock(
                        kind=BlockKind.DEFINITION,
                        term="Диафиз",
                        text="Средняя часть трубчатой кости.",
                        origin=BlockOrigin.MODEL_ADDED,
                    ),
                ),
            ),
        ),
    )

    restored = parse_notes_payload(notes_payload(notes), claims_count=0)

    assert restored == notes
    payload_blocks = notes_payload(notes)["sections"][0]["blocks"]
    assert payload_blocks[0]["origin"] == "lecture"
    assert payload_blocks[1]["origin"] == "model_added"


def test_emphasis_in_non_prose_fields_is_normalized_on_parse() -> None:
    payload = a_notes_payload(
        [
            a_block_payload(
                kind="definition",
                term="**Диафиз**",
                text="Средняя часть **трубчатой** кости.",
            )
        ]
    )

    notes = parse_notes_payload(payload, claims_count=1)

    block = notes.sections[0].blocks[0]
    assert block.term == "Диафиз"
    assert block.text == "Средняя часть **трубчатой** кости."


def test_payload_without_origin_key_parses_as_none() -> None:
    payload = a_notes_payload([a_block_payload(kind="fact")])

    notes = parse_notes_payload(payload, claims_count=1)

    assert notes.sections[0].blocks[0].origin is None


def test_figure_without_source_ref_is_rejected() -> None:
    payload = a_notes_payload(
        [a_block_payload(kind="figure", text=None, image_path="frames/f.png", source_ref=None)]
    )

    with pytest.raises(NotesArtifactError, match="source_ref"):
        parse_notes_payload(payload, claims_count=1)


def test_factcheck_note_with_out_of_range_claim_ref_is_rejected() -> None:
    payload = a_notes_payload([a_block_payload(kind="factcheck_note", claim_ref=5)])

    with pytest.raises(NotesArtifactError, match="claim_ref"):
        parse_notes_payload(payload, claims_count=2)


def test_factcheck_note_with_negative_claim_ref_is_rejected() -> None:
    payload = a_notes_payload([a_block_payload(kind="factcheck_note", claim_ref=-1)])

    with pytest.raises(NotesArtifactError, match="claim_ref"):
        parse_notes_payload(payload, claims_count=2)


def a_section_payload(section_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "section_id": section_id,
        "title": f"Раздел {section_id}",
        "source_spans": [[0.0, 60.0]],
        "subsections": [],
        "blocks": [a_block_payload()],
    }
    payload.update(overrides)
    return payload


def test_flat_payload_without_subsections_key_is_accepted() -> None:
    payload = a_notes_payload([a_block_payload()])

    notes = parse_notes_payload(payload, claims_count=1)

    assert notes.sections[0].subsections == ()


def test_depth_three_nesting_is_rejected() -> None:
    payload = {
        "title": "Введение",
        "language": "ru",
        "sections": [
            a_section_payload(
                "s1",
                subsections=[
                    a_section_payload(
                        "s1.1", subsections=[a_section_payload("s1.1.1")]
                    )
                ],
            )
        ],
    }

    with pytest.raises(NotesArtifactError, match="depth"):
        parse_notes_payload(payload, claims_count=1)


def test_duplicate_section_id_across_tree_is_rejected() -> None:
    payload = {
        "title": "Введение",
        "language": "ru",
        "sections": [
            a_section_payload("s1", subsections=[a_section_payload("s1")]),
        ],
    }

    with pytest.raises(NotesArtifactError, match="unique"):
        parse_notes_payload(payload, claims_count=1)


def test_dangling_claim_ref_inside_subsection_is_rejected() -> None:
    payload = {
        "title": "Введение",
        "language": "ru",
        "sections": [
            a_section_payload(
                "s1",
                subsections=[
                    a_section_payload(
                        "s1.1",
                        blocks=[a_block_payload(kind="factcheck_note", claim_ref=7)],
                    )
                ],
            )
        ],
    }

    with pytest.raises(NotesArtifactError, match="claim_ref"):
        parse_notes_payload(payload, claims_count=1)


def test_unpaired_emphasis_inside_subsection_is_rejected() -> None:
    payload = {
        "title": "Введение",
        "language": "ru",
        "sections": [
            a_section_payload(
                "s1",
                subsections=[
                    a_section_payload(
                        "s1.1", blocks=[a_block_payload(text="**Непарный маркер.")]
                    )
                ],
            )
        ],
    }

    with pytest.raises(NotesArtifactError, match=r"\*\*"):
        parse_notes_payload(payload, claims_count=1)


def test_definition_without_term_is_rejected() -> None:
    payload = a_notes_payload([a_block_payload(kind="definition", term=None)])

    with pytest.raises(NotesArtifactError, match="term"):
        parse_notes_payload(payload, claims_count=1)


def test_term_on_non_definition_block_is_rejected() -> None:
    payload = a_notes_payload([a_block_payload(kind="prose", term="Энергия")])

    with pytest.raises(NotesArtifactError, match="term"):
        parse_notes_payload(payload, claims_count=1)


def test_unpaired_emphasis_marker_is_rejected() -> None:
    payload = a_notes_payload(
        [a_block_payload(text="**Энергия сохраняется, а энтропия растёт.")]
    )

    with pytest.raises(NotesArtifactError, match=r"\*\*"):
        parse_notes_payload(payload, claims_count=1)


def test_paired_emphasis_markers_are_accepted() -> None:
    payload = a_notes_payload(
        [a_block_payload(text="**Энергия** сохраняется, **энтропия** растёт.")]
    )

    notes = parse_notes_payload(payload, claims_count=1)

    assert "**Энергия**" in notes.sections[0].blocks[0].text


def test_missing_required_field_is_rejected() -> None:
    payload = a_notes_payload([a_block_payload()])
    del payload["title"]

    with pytest.raises(NotesArtifactError, match="title"):
        parse_notes_payload(payload, claims_count=1)


def test_unknown_block_kind_is_rejected() -> None:
    payload = a_notes_payload([a_block_payload(kind="sidebar")])

    with pytest.raises(NotesArtifactError, match="sidebar"):
        parse_notes_payload(payload, claims_count=1)


def a_structured_notes() -> Notes:
    return Notes(
        title="Анатомия",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Кости предплечья",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=(
                    NoteBlock(
                        kind=BlockKind.TABLE,
                        caption="Сравнение костей",
                        table=TableData(
                            columns=("Кость", "Положение"),
                            rows=(("Лучевая", "латерально"), ("Локтевая", "медиально")),
                        ),
                    ),
                    NoteBlock(
                        kind=BlockKind.DIAGRAM,
                        caption="Классификация",
                        diagram=DiagramData(
                            kind=DiagramKind.HIERARCHY,
                            nodes=(DiagramNode("bones", "Кости"), DiagramNode("long", "Трубчатые")),
                            edges=(DiagramEdge("bones", "long", None),),
                        ),
                    ),
                    NoteBlock(
                        kind=BlockKind.CHART,
                        caption="Рост",
                        chart=ChartData(
                            kind=ChartKind.LINE,
                            categories=("2020", "2021"),
                            series=(ChartSeries("Длина", (1.0, 2.5)),),
                            x_title="Год",
                            y_title=None,
                        ),
                    ),
                    NoteBlock(
                        kind=BlockKind.FIGURE,
                        image_path="images/gen.png",
                        caption="Лучевая кость",
                        source_ref="generated:codex",
                        provenance=FigureProvenance.GENERATED,
                    ),
                ),
            ),
        ),
    )


def test_structured_blocks_round_trip() -> None:
    notes = a_structured_notes()

    restored = parse_notes_payload(notes_payload(notes), claims_count=0)

    assert restored == notes


def test_structured_payload_uses_contract_field_names() -> None:
    blocks = notes_payload(a_structured_notes())["sections"][0]["blocks"]

    assert blocks[0]["table"] == {
        "columns": ["Кость", "Положение"],
        "rows": [["Лучевая", "латерально"], ["Локтевая", "медиально"]],
    }
    assert blocks[1]["diagram"] == {
        "kind": "hierarchy",
        "nodes": [{"id": "bones", "label": "Кости"}, {"id": "long", "label": "Трубчатые"}],
        "edges": [{"source": "bones", "target": "long", "label": None}],
    }
    assert blocks[2]["chart"] == {
        "kind": "line",
        "categories": ["2020", "2021"],
        "series": [{"name": "Длина", "values": [1.0, 2.5]}],
        "x_title": "Год",
        "y_title": None,
    }
    assert blocks[3]["provenance"] == "generated"
    assert blocks[0]["provenance"] is None
    assert blocks[3]["table"] is None


def test_payload_without_structured_keys_still_parses() -> None:
    payload = a_notes_payload(
        [a_block_payload(kind="figure", text=None, image_path="frames/f.png", source_ref="video 00:00:30")]
    )

    notes = parse_notes_payload(payload, claims_count=1)

    figure = notes.sections[0].blocks[0]
    assert figure.provenance is FigureProvenance.VIDEO_FRAME
    assert figure.table is None


def test_explicit_provenance_round_trips_for_commons_figure() -> None:
    payload = a_notes_payload(
        [
            a_block_payload(
                kind="figure",
                text=None,
                image_path="images/x.jpg",
                source_ref="https://commons.wikimedia.org/wiki/File:X.jpg",
                provenance="commons",
            )
        ]
    )

    notes = parse_notes_payload(payload, claims_count=1)

    assert notes.sections[0].blocks[0].provenance is FigureProvenance.COMMONS


@pytest.mark.parametrize(
    "kind, field_name, raw_value, message",
    [
        (
            "table",
            "table",
            {"columns": ["a", "b"], "rows": [["1"]]},
            "cells as columns",
        ),
        (
            "diagram",
            "diagram",
            {
                "kind": "flow",
                "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                "edges": [{"source": "a", "target": "zzz", "label": None}],
            },
            "undeclared node",
        ),
        (
            "diagram",
            "diagram",
            {"kind": "flow", "nodes": [{"id": "a", "label": "A"}], "edges": []},
            "two nodes",
        ),
        (
            "chart",
            "chart",
            {
                "kind": "bar",
                "categories": ["x", "y"],
                "series": [{"name": "s", "values": [1]}],
                "x_title": None,
                "y_title": None,
            },
            "values as categories",
        ),
        ("chart", "chart", {"kind": "pie", "categories": ["x"], "series": []}, "pie"),
    ],
    ids=["ragged-table", "dangling-edge", "single-node", "series-mismatch", "unknown-chart-kind"],
)
def test_structured_block_violations_are_rejected(
    kind: str, field_name: str, raw_value: dict[str, object], message: str
) -> None:
    payload = a_notes_payload([a_block_payload(kind=kind, text=None, **{field_name: raw_value})])

    with pytest.raises(NotesArtifactError, match=message):
        parse_notes_payload(payload, claims_count=1)


def test_structured_block_without_its_data_is_rejected() -> None:
    payload = a_notes_payload([a_block_payload(kind="table", text=None)])

    with pytest.raises(NotesArtifactError, match="table"):
        parse_notes_payload(payload, claims_count=1)


# @covers analysis:DLT-031
def test_origin_on_a_non_fact_block_is_normalized_away() -> None:
    raw_block = {
        "kind": "prose",
        "text": "t",
        "term": None,
        "image_path": None,
        "caption": None,
        "source_ref": None,
        "claim_ref": None,
        "origin": "lecture",
    }

    block = parse_block_payload(raw_block)

    assert block.origin is None
