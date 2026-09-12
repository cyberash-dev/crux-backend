from dataclasses import dataclass
from enum import StrEnum

from konspekt.shared.timecode import TimeRange


class BlockKind(StrEnum):
    PROSE = "prose"
    DEFINITION = "definition"
    FACT = "fact"
    FIGURE = "figure"
    FACTCHECK_NOTE = "factcheck_note"
    TABLE = "table"
    DIAGRAM = "diagram"
    CHART = "chart"


class FigureProvenance(StrEnum):
    VIDEO_FRAME = "video_frame"
    COMMONS = "commons"
    GENERATED = "generated"


class BlockOrigin(StrEnum):
    LECTURE = "lecture"
    MODEL_ADDED = "model_added"


_ORIGIN_KINDS = (BlockKind.FACT, BlockKind.DEFINITION)


VIDEO_SOURCE_PREFIX = "video "
GENERATED_SOURCE_PREFIX = "generated:"
_HTTPS_PREFIX = "https://"


class DiagramKind(StrEnum):
    HIERARCHY = "hierarchy"
    FLOW = "flow"


class ChartKind(StrEnum):
    BAR = "bar"
    LINE = "line"


@dataclass(frozen=True, slots=True)
class TableData:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.columns or not self.rows:
            raise ValueError("table requires at least one column and one row")
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("table rows must have exactly as many cells as columns")


@dataclass(frozen=True, slots=True)
class DiagramNode:
    id: str
    label: str


@dataclass(frozen=True, slots=True)
class DiagramEdge:
    source: str
    target: str
    label: str | None = None


@dataclass(frozen=True, slots=True)
class DiagramData:
    kind: DiagramKind
    nodes: tuple[DiagramNode, ...]
    edges: tuple[DiagramEdge, ...]

    def __post_init__(self) -> None:
        if len(self.nodes) < 2:
            raise ValueError("diagram requires at least two nodes")
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("diagram node ids must be unique")
        declared = set(node_ids)
        for edge in self.edges:
            if edge.source not in declared or edge.target not in declared:
                raise ValueError(
                    f"diagram edge {edge.source!r} -> {edge.target!r} references an undeclared node"
                )


@dataclass(frozen=True, slots=True)
class ChartSeries:
    name: str
    values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ChartData:
    kind: ChartKind
    categories: tuple[str, ...]
    series: tuple[ChartSeries, ...]
    x_title: str | None = None
    y_title: str | None = None

    def __post_init__(self) -> None:
        if not self.categories:
            raise ValueError("chart requires at least one category")
        if not self.series:
            raise ValueError("chart requires at least one series")
        if any(len(one_series.values) != len(self.categories) for one_series in self.series):
            raise ValueError("chart series must have exactly as many values as categories")


_STRUCTURED_FIELD_BY_KIND = {
    BlockKind.TABLE: "table",
    BlockKind.DIAGRAM: "diagram",
    BlockKind.CHART: "chart",
}


@dataclass(frozen=True, slots=True)
class NoteBlock:
    kind: BlockKind
    text: str | None = None
    term: str | None = None
    image_path: str | None = None
    caption: str | None = None
    source_ref: str | None = None
    claim_ref: int | None = None
    provenance: FigureProvenance | None = None
    origin: BlockOrigin | None = None
    table: TableData | None = None
    diagram: DiagramData | None = None
    chart: ChartData | None = None

    def __post_init__(self) -> None:
        if self.kind is BlockKind.FIGURE and (self.image_path is None or self.source_ref is None):
            raise ValueError("figure block requires image_path and source_ref")
        if self.kind is BlockKind.FACTCHECK_NOTE and (self.text is None or self.claim_ref is None):
            raise ValueError("factcheck_note block requires text and claim_ref")
        if self.kind in (BlockKind.PROSE, BlockKind.FACT) and self.text is None:
            raise ValueError(f"{self.kind} block requires text")
        if self.kind is BlockKind.DEFINITION and (self.term is None or self.text is None):
            raise ValueError("definition block requires term and text")
        if self.kind is not BlockKind.DEFINITION and self.term is not None:
            raise ValueError("term is allowed on definition blocks only")
        if self.origin is not None and self.kind not in _ORIGIN_KINDS:
            raise ValueError("origin is allowed on fact and definition blocks only")
        self._validate_provenance()
        self._validate_structured_data()

    def _validate_provenance(self) -> None:
        if self.kind is not BlockKind.FIGURE:
            if self.provenance is not None:
                raise ValueError("provenance is allowed on figure blocks only")
            return
        if self.provenance is None:
            inferred = _inferred_provenance(self.source_ref or "")
            if inferred is None:
                raise ValueError(
                    f"figure block with source_ref {self.source_ref!r} requires an explicit provenance"
                )
            object.__setattr__(self, "provenance", inferred)

    def _validate_structured_data(self) -> None:
        for kind, field_name in _STRUCTURED_FIELD_BY_KIND.items():
            value = getattr(self, field_name)
            if self.kind is kind and value is None:
                raise ValueError(f"{kind} block requires {field_name} data")
            if self.kind is not kind and value is not None:
                raise ValueError(f"{field_name} is allowed on {kind} blocks only")


def _inferred_provenance(source_ref: str) -> FigureProvenance | None:
    if source_ref.startswith(VIDEO_SOURCE_PREFIX):
        return FigureProvenance.VIDEO_FRAME
    if source_ref.startswith(GENERATED_SOURCE_PREFIX):
        return FigureProvenance.GENERATED
    if source_ref.startswith(_HTTPS_PREFIX):
        return FigureProvenance.COMMONS
    return None


@dataclass(frozen=True, slots=True)
class NoteSection:
    section_id: str
    title: str
    source_spans: tuple[TimeRange, ...]
    blocks: tuple[NoteBlock, ...]
    subsections: tuple["NoteSection", ...] = ()

    def __post_init__(self) -> None:
        if any(subsection.subsections for subsection in self.subsections):
            raise ValueError("subsections must not nest further (maximum depth is 2)")


@dataclass(frozen=True, slots=True)
class Notes:
    title: str
    language: str
    sections: tuple[NoteSection, ...]

    def __post_init__(self) -> None:
        all_ids = [section.section_id for section in self.all_sections()]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("section_id values must be unique across the whole tree")

    def all_sections(self) -> tuple[NoteSection, ...]:
        flattened: list[NoteSection] = []
        for section in self.sections:
            flattened.append(section)
            flattened.extend(section.subsections)
        return tuple(flattened)

    def owning_top_section_id(self, section_id: str) -> str | None:
        for section in self.sections:
            if section.section_id == section_id:
                return section.section_id
            if any(sub.section_id == section_id for sub in section.subsections):
                return section.section_id
        return None
