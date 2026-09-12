# @covers analysis:DLT-031
# @covers analysis:CON-022
from konspekt.features.notes.application.emphasis import strip_non_prose_emphasis
from konspekt.features.notes.domain.notes import (
    BlockKind,
    ChartData,
    ChartKind,
    ChartSeries,
    DiagramData,
    DiagramEdge,
    DiagramKind,
    DiagramNode,
    NoteBlock,
    NoteSection,
    Notes,
    TableData,
)
from konspekt.shared.timecode import TimeRange


def notes_with_blocks(*blocks: NoteBlock) -> Notes:
    return Notes(
        title="Анатомия",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Кости",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=blocks,
            ),
        ),
    )


def test_term_emphasis_is_stripped_and_definition_text_kept() -> None:
    notes = notes_with_blocks(
        NoteBlock(
            kind=BlockKind.DEFINITION,
            term="**Диафиз**",
            text="Средняя часть **трубчатой** кости.",
        )
    )

    stripped = strip_non_prose_emphasis(notes)

    block = stripped.sections[0].blocks[0]
    assert block.term == "Диафиз"
    assert block.text == "Средняя часть **трубчатой** кости."


def test_caption_emphasis_is_stripped() -> None:
    notes = notes_with_blocks(
        NoteBlock(
            kind=BlockKind.FIGURE,
            image_path="frames/frame_30.png",
            caption="**Схема** цикла",
            source_ref="video 00:00:30",
        )
    )

    stripped = strip_non_prose_emphasis(notes)

    assert stripped.sections[0].blocks[0].caption == "Схема цикла"


def test_table_columns_and_cells_emphasis_is_stripped() -> None:
    notes = notes_with_blocks(
        NoteBlock(
            kind=BlockKind.TABLE,
            caption="Сравнение",
            table=TableData(
                columns=("**Кость**", "Положение"),
                rows=(("**Лучевая**", "латерально"),),
            ),
        )
    )

    stripped = strip_non_prose_emphasis(notes)

    table = stripped.sections[0].blocks[0].table
    assert table is not None
    assert table.columns == ("Кость", "Положение")
    assert table.rows == (("Лучевая", "латерально"),)


def test_diagram_node_and_edge_label_emphasis_is_stripped() -> None:
    notes = notes_with_blocks(
        NoteBlock(
            kind=BlockKind.DIAGRAM,
            caption="Классификация",
            diagram=DiagramData(
                kind=DiagramKind.FLOW,
                nodes=(
                    DiagramNode("a", "**Вдох**"),
                    DiagramNode("b", "Выдох"),
                ),
                edges=(DiagramEdge("a", "b", "**затем**"),),
            ),
        )
    )

    stripped = strip_non_prose_emphasis(notes)

    diagram = stripped.sections[0].blocks[0].diagram
    assert diagram is not None
    assert diagram.nodes[0].label == "Вдох"
    assert diagram.edges[0].label == "затем"


def test_chart_names_titles_and_categories_emphasis_is_stripped() -> None:
    notes = notes_with_blocks(
        NoteBlock(
            kind=BlockKind.CHART,
            caption="Рост",
            chart=ChartData(
                kind=ChartKind.BAR,
                categories=("**2020**", "2021"),
                series=(ChartSeries("**Длина**", (1.0, 2.0)),),
                x_title="**Год**",
                y_title="**см**",
            ),
        )
    )

    stripped = strip_non_prose_emphasis(notes)

    chart = stripped.sections[0].blocks[0].chart
    assert chart is not None
    assert chart.categories == ("2020", "2021")
    assert chart.series[0].name == "Длина"
    assert chart.x_title == "Год"
    assert chart.y_title == "см"


def test_prose_capable_text_fields_keep_emphasis() -> None:
    notes = notes_with_blocks(
        NoteBlock(kind=BlockKind.PROSE, text="**Энергия** сохраняется."),
        NoteBlock(kind=BlockKind.FACT, text="**Джоуль** варил пиво."),
        NoteBlock(
            kind=BlockKind.FACTCHECK_NOTE,
            text="**Спорное** утверждение.",
            claim_ref=0,
        ),
    )

    stripped = strip_non_prose_emphasis(notes)

    assert [block.text for block in stripped.sections[0].blocks] == [
        "**Энергия** сохраняется.",
        "**Джоуль** варил пиво.",
        "**Спорное** утверждение.",
    ]


def test_subsection_blocks_are_stripped_too() -> None:
    notes = Notes(
        title="Анатомия",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Кости",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=(),
                subsections=(
                    NoteSection(
                        section_id="s1.1",
                        title="Диафиз",
                        source_spans=(TimeRange(0.0, 30.0),),
                        blocks=(
                            NoteBlock(
                                kind=BlockKind.DEFINITION,
                                term="**Диафиз**",
                                text="Средняя часть кости.",
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    stripped = strip_non_prose_emphasis(notes)

    assert stripped.sections[0].subsections[0].blocks[0].term == "Диафиз"


def test_clean_notes_are_returned_unchanged() -> None:
    notes = notes_with_blocks(
        NoteBlock(kind=BlockKind.DEFINITION, term="Диафиз", text="Средняя часть кости.")
    )

    stripped = strip_non_prose_emphasis(notes)

    assert stripped == notes
