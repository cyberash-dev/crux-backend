# @covers analysis:CON-022
# @covers analysis:REQ-026
import pytest

from konspekt.features.notes.domain.notes import (
    BlockKind,
    ChartData,
    ChartKind,
    ChartSeries,
    DiagramData,
    DiagramEdge,
    DiagramKind,
    DiagramNode,
    FigureProvenance,
    NoteBlock,
    TableData,
)


def a_hierarchy(edges: tuple[DiagramEdge, ...]) -> DiagramData:
    return DiagramData(
        kind=DiagramKind.HIERARCHY,
        nodes=(DiagramNode("a", "A"), DiagramNode("b", "B")),
        edges=edges,
    )


def test_table_block_carries_columns_and_rows() -> None:
    block = NoteBlock(
        kind=BlockKind.TABLE,
        caption="Кости",
        table=TableData(columns=("Кость", "Тип"), rows=(("Лучевая", "трубчатая"),)),
    )

    assert block.table is not None
    assert block.table.rows[0] == ("Лучевая", "трубчатая")


@pytest.mark.parametrize(
    "columns, rows",
    [
        (("a", "b"), (("1",),)),
        ((), (("1",),)),
        (("a",), ()),
    ],
    ids=["ragged", "no-columns", "no-rows"],
)
def test_invalid_table_data_is_rejected(columns: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> None:
    with pytest.raises(ValueError, match="table"):
        TableData(columns=columns, rows=rows)


def test_diagram_with_declared_nodes_and_edges_is_accepted() -> None:
    diagram = a_hierarchy((DiagramEdge("a", "b", None),))

    assert diagram.edges[0].target == "b"


def test_diagram_edge_to_undeclared_node_is_rejected() -> None:
    with pytest.raises(ValueError, match="node"):
        a_hierarchy((DiagramEdge("a", "zzz", None),))


def test_single_node_diagram_is_rejected() -> None:
    with pytest.raises(ValueError, match="two nodes"):
        DiagramData(kind=DiagramKind.FLOW, nodes=(DiagramNode("a", "A"),), edges=())


def test_duplicate_node_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        DiagramData(
            kind=DiagramKind.FLOW,
            nodes=(DiagramNode("a", "A"), DiagramNode("a", "B")),
            edges=(),
        )


def test_chart_series_must_match_categories() -> None:
    with pytest.raises(ValueError, match="categories"):
        ChartData(
            kind=ChartKind.BAR,
            categories=("x", "y"),
            series=(ChartSeries("s", (1.0,)),),
        )


def test_chart_without_series_is_rejected() -> None:
    with pytest.raises(ValueError, match="series"):
        ChartData(kind=ChartKind.LINE, categories=("x",), series=())


def test_structured_block_requires_its_data() -> None:
    with pytest.raises(ValueError, match="chart block requires"):
        NoteBlock(kind=BlockKind.CHART, caption="c")


def test_structured_data_on_foreign_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="table is allowed"):
        NoteBlock(
            kind=BlockKind.PROSE,
            text="t",
            table=TableData(columns=("a",), rows=(("1",),)),
        )


def test_figure_provenance_is_inferred_from_source_ref() -> None:
    frame_figure = NoteBlock(kind=BlockKind.FIGURE, image_path="f.jpg", source_ref="video 00:00:01")
    generated_figure = NoteBlock(kind=BlockKind.FIGURE, image_path="g.png", source_ref="generated:codex")

    assert frame_figure.provenance is FigureProvenance.VIDEO_FRAME
    assert generated_figure.provenance is FigureProvenance.GENERATED


def test_figure_with_unrecognizable_source_needs_explicit_provenance() -> None:
    with pytest.raises(ValueError, match="provenance"):
        NoteBlock(kind=BlockKind.FIGURE, image_path="f.jpg", source_ref="somewhere")


def test_provenance_on_non_figure_is_rejected() -> None:
    with pytest.raises(ValueError, match="provenance"):
        NoteBlock(kind=BlockKind.PROSE, text="t", provenance=FigureProvenance.COMMONS)
