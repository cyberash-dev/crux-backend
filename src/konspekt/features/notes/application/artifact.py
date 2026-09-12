from collections.abc import Mapping

from konspekt.features.factcheck.domain.claims import Verdict
from konspekt.features.notes.application.emphasis import strip_non_prose_emphasis
from konspekt.features.notes.domain.audit import AdditionAction, VerifiedAddition
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


class NotesArtifactError(Exception):
    pass


def notes_payload(notes: Notes) -> dict[str, object]:
    return {
        "title": notes.title,
        "language": notes.language,
        "sections": [_section_payload(section) for section in notes.sections],
    }


def parse_notes_payload(payload: Mapping[str, object], claims_count: int) -> Notes:
    try:
        notes = Notes(
            title=payload["title"],
            language=payload["language"],
            sections=tuple(_parse_section(raw_section) for raw_section in payload["sections"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise NotesArtifactError(f"invalid notes payload: {error!r}") from error
    _reject_dangling_claim_refs(notes, claims_count)
    _reject_unbalanced_emphasis(notes)
    return strip_non_prose_emphasis(notes)


def _section_payload(section: NoteSection) -> dict[str, object]:
    return {
        "section_id": section.section_id,
        "title": section.title,
        "source_spans": [
            [span.start_seconds, span.end_seconds] for span in section.source_spans
        ],
        "subsections": [
            _section_payload(subsection) for subsection in section.subsections
        ],
        "blocks": [_block_payload(block) for block in section.blocks],
    }


def _block_payload(block: NoteBlock) -> dict[str, object]:
    return {
        "kind": block.kind.value,
        "text": block.text,
        "term": block.term,
        "image_path": block.image_path,
        "caption": block.caption,
        "source_ref": block.source_ref,
        "claim_ref": block.claim_ref,
        "provenance": block.provenance.value if block.provenance is not None else None,
        "origin": block.origin.value if block.origin is not None else None,
        "table": _table_payload(block.table) if block.table is not None else None,
        "diagram": _diagram_payload(block.diagram) if block.diagram is not None else None,
        "chart": _chart_payload(block.chart) if block.chart is not None else None,
    }


def _table_payload(table: TableData) -> dict[str, object]:
    return {
        "columns": list(table.columns),
        "rows": [list(row) for row in table.rows],
    }


def _diagram_payload(diagram: DiagramData) -> dict[str, object]:
    return {
        "kind": diagram.kind.value,
        "nodes": [{"id": node.id, "label": node.label} for node in diagram.nodes],
        "edges": [
            {"source": edge.source, "target": edge.target, "label": edge.label}
            for edge in diagram.edges
        ],
    }


def _chart_payload(chart: ChartData) -> dict[str, object]:
    return {
        "kind": chart.kind.value,
        "categories": list(chart.categories),
        "series": [
            {"name": one_series.name, "values": list(one_series.values)}
            for one_series in chart.series
        ],
        "x_title": chart.x_title,
        "y_title": chart.y_title,
    }


def _parse_section(raw_section: Mapping[str, object]) -> NoteSection:
    return NoteSection(
        section_id=raw_section["section_id"],
        title=raw_section["title"],
        source_spans=tuple(
            TimeRange(start_seconds, end_seconds)
            for start_seconds, end_seconds in raw_section["source_spans"]
        ),
        subsections=tuple(
            _parse_section(raw_subsection)
            for raw_subsection in raw_section.get("subsections", [])
        ),
        blocks=tuple(_parse_block(raw_block) for raw_block in raw_section["blocks"]),
    )


def parse_block_payload(raw_block: Mapping[str, object]) -> NoteBlock:
    try:
        return _parse_block(raw_block)
    except (KeyError, TypeError, ValueError) as error:
        raise NotesArtifactError(f"invalid note block payload: {error!r}") from error


def has_unbalanced_emphasis(text: str) -> bool:
    return text.count("**") % 2 != 0


def _parse_block(raw_block: Mapping[str, object]) -> NoteBlock:
    raw_provenance = raw_block.get("provenance")
    raw_origin = raw_block.get("origin")
    if raw_block["kind"] not in (BlockKind.FACT.value, BlockKind.DEFINITION.value):
        raw_origin = None
    raw_table = raw_block.get("table")
    raw_diagram = raw_block.get("diagram")
    raw_chart = raw_block.get("chart")
    return NoteBlock(
        kind=BlockKind(raw_block["kind"]),
        text=raw_block["text"],
        term=raw_block["term"],
        image_path=raw_block["image_path"],
        caption=raw_block["caption"],
        source_ref=raw_block["source_ref"],
        claim_ref=raw_block["claim_ref"],
        provenance=FigureProvenance(raw_provenance) if raw_provenance is not None else None,
        origin=BlockOrigin(raw_origin) if raw_origin is not None else None,
        table=_parse_table(raw_table) if raw_table is not None else None,
        diagram=_parse_diagram(raw_diagram) if raw_diagram is not None else None,
        chart=_parse_chart(raw_chart) if raw_chart is not None else None,
    )


def _parse_table(raw_table: Mapping[str, object]) -> TableData:
    return TableData(
        columns=tuple(str(column) for column in raw_table["columns"]),
        rows=tuple(tuple(str(cell) for cell in row) for row in raw_table["rows"]),
    )


def _parse_diagram(raw_diagram: Mapping[str, object]) -> DiagramData:
    return DiagramData(
        kind=DiagramKind(raw_diagram["kind"]),
        nodes=tuple(
            DiagramNode(id=str(raw_node["id"]), label=str(raw_node["label"]))
            for raw_node in raw_diagram["nodes"]
        ),
        edges=tuple(
            DiagramEdge(
                source=str(raw_edge["source"]),
                target=str(raw_edge["target"]),
                label=raw_edge.get("label"),
            )
            for raw_edge in raw_diagram["edges"]
        ),
    )


def _parse_chart(raw_chart: Mapping[str, object]) -> ChartData:
    return ChartData(
        kind=ChartKind(raw_chart["kind"]),
        categories=tuple(str(category) for category in raw_chart["categories"]),
        series=tuple(
            ChartSeries(
                name=str(raw_series["name"]),
                values=tuple(float(value) for value in raw_series["values"]),
            )
            for raw_series in raw_chart["series"]
        ),
        x_title=raw_chart.get("x_title"),
        y_title=raw_chart.get("y_title"),
    )


def _reject_dangling_claim_refs(notes: Notes, claims_count: int) -> None:
    for section in notes.all_sections():
        for block in section.blocks:
            if block.claim_ref is None:
                continue
            if not 0 <= block.claim_ref < claims_count:
                raise NotesArtifactError(
                    f"claim_ref {block.claim_ref} in section {section.section_id!r} "
                    f"is outside the claims list of length {claims_count}"
                )


def _reject_unbalanced_emphasis(notes: Notes) -> None:
    for section in notes.all_sections():
        for block in section.blocks:
            if block.text is not None and has_unbalanced_emphasis(block.text):
                raise NotesArtifactError(
                    f"block text in section {section.section_id!r} carries an "
                    f"unpaired ** emphasis marker: {block.text!r}"
                )


def verified_additions_payload(
    additions: tuple[VerifiedAddition, ...]
) -> list[dict[str, object]]:
    return [
        {
            "text": addition.text,
            "origin": addition.origin.value,
            "kind": addition.kind.value,
            "verdict": addition.verdict.value,
            "sources": list(addition.sources),
            "annotation": addition.annotation,
            "action": addition.action.value,
        }
        for addition in additions
    ]


def parse_verified_additions(payload: Mapping[str, object]) -> tuple[VerifiedAddition, ...]:
    raw_additions = payload.get("verified_additions", [])
    try:
        return tuple(
            VerifiedAddition(
                text=raw["text"],
                origin=BlockOrigin(raw["origin"]),
                kind=BlockKind(raw["kind"]),
                verdict=Verdict(raw["verdict"]),
                sources=tuple(raw["sources"]),
                annotation=raw["annotation"],
                action=AdditionAction(raw["action"]),
            )
            for raw in raw_additions
        )
    except (KeyError, TypeError, ValueError) as error:
        raise NotesArtifactError(f"invalid verified_additions payload: {error!r}") from error
