from dataclasses import replace

from konspekt.features.notes.domain.notes import (
    ChartData,
    ChartSeries,
    DiagramData,
    DiagramEdge,
    DiagramNode,
    NoteBlock,
    NoteSection,
    Notes,
    TableData,
)

_EMPHASIS_MARKER = "**"


def strip_non_prose_emphasis(notes: Notes) -> Notes:
    return replace(
        notes,
        sections=tuple(_stripped_section(section) for section in notes.sections),
    )


def _stripped_section(section: NoteSection) -> NoteSection:
    return replace(
        section,
        blocks=tuple(_stripped_block(block) for block in section.blocks),
        subsections=tuple(
            _stripped_section(subsection) for subsection in section.subsections
        ),
    )


def _stripped_block(block: NoteBlock) -> NoteBlock:
    return replace(
        block,
        term=_stripped(block.term),
        caption=_stripped(block.caption),
        table=_stripped_table(block.table) if block.table is not None else None,
        diagram=_stripped_diagram(block.diagram) if block.diagram is not None else None,
        chart=_stripped_chart(block.chart) if block.chart is not None else None,
    )


def _stripped_table(table: TableData) -> TableData:
    return TableData(
        columns=tuple(_stripped_text(column) for column in table.columns),
        rows=tuple(
            tuple(_stripped_text(cell) for cell in row) for row in table.rows
        ),
    )


def _stripped_diagram(diagram: DiagramData) -> DiagramData:
    return DiagramData(
        kind=diagram.kind,
        nodes=tuple(
            DiagramNode(id=node.id, label=_stripped_text(node.label))
            for node in diagram.nodes
        ),
        edges=tuple(
            DiagramEdge(
                source=edge.source, target=edge.target, label=_stripped(edge.label)
            )
            for edge in diagram.edges
        ),
    )


def _stripped_chart(chart: ChartData) -> ChartData:
    return ChartData(
        kind=chart.kind,
        categories=tuple(_stripped_text(category) for category in chart.categories),
        series=tuple(
            ChartSeries(name=_stripped_text(one_series.name), values=one_series.values)
            for one_series in chart.series
        ),
        x_title=_stripped(chart.x_title),
        y_title=_stripped(chart.y_title),
    )


def _stripped(text: str | None) -> str | None:
    return _stripped_text(text) if text is not None else None


def _stripped_text(text: str) -> str:
    return text.replace(_EMPHASIS_MARKER, "")
