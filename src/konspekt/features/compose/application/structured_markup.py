from collections import deque
from collections.abc import Iterable, Mapping

from konspekt.features.compose.application.typst_text import escaped
from konspekt.features.notes.domain.notes import (
    ChartData,
    ChartKind,
    ChartSeries,
    DiagramData,
    DiagramKind,
    TableData,
)

FLETCHER_IMPORT = '#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge'
LILAQ_IMPORT = '#import "@preview/lilaq:0.5.0" as lq'

_FLOW_NODES_PER_ROW = 4
_WRAP_LABELS_LONGER_THAN = 16
_WRAPPED_LABEL_WIDTH = "8em"
_WRAPPED_EDGE_LABEL_WIDTH = "7em"
_BAR_GROUP_WIDTH = 0.8
_EDGE_MARK = '"-|>"'

Position = tuple[float, int]


def table_markup(table: TableData, caption: str) -> str:
    header_cells = ", ".join(f"[*{escaped(column)}*]" for column in table.columns)
    row_lines = [
        "    " + ", ".join(f"[{escaped(cell)}]" for cell in row) + ","
        for row in table.rows
    ]
    return "\n".join(
        [
            "#figure(",
            f"  table(columns: {len(table.columns)}, stroke: 0.5pt + luma(180), "
            "inset: 6pt, align: left,",
            f"    table.header({header_cells}),",
            *row_lines,
            "  ),",
            f"  caption: {_caption(caption)},",
            ")",
        ]
    )


def diagram_markup(diagram: DiagramData, caption: str) -> str:
    positions = _node_positions(diagram)
    node_lines = [
        f"      node({_point(positions[node.id])}, {_node_label(node.label)}),"
        for node in diagram.nodes
    ]
    edge_lines = [
        f"      edge({_point(positions[edge.source])}, {_point(positions[edge.target])}, "
        f"{_EDGE_MARK}{_edge_label(edge.label)}),"
        for edge in diagram.edges
    ]
    return "\n".join(
        [
            "#figure(",
            "  layout(size => {",
            "    let drawing = diagram(spacing: (2.4em, 1.6em), node-stroke: 0.6pt, "
            "node-inset: 6pt, node-corner-radius: 3pt,",
            *node_lines,
            *edge_lines,
            "    )",
            "    let natural = measure(drawing)",
            "    if natural.width > size.width {",
            "      scale(x: size.width / natural.width * 100%, "
            "y: size.width / natural.width * 100%, reflow: true, drawing)",
            "    } else { drawing }",
            "  }),",
            f"  caption: {_caption(caption)},",
            ")",
        ]
    )


def chart_markup(chart: ChartData, caption: str) -> str:
    category_indices = tuple(range(len(chart.categories)))
    ticks = _typst_array(
        f"({index}, [{escaped(category)}])"
        for index, category in zip(category_indices, chart.categories, strict=True)
    )
    xs = _typst_array(str(index) for index in category_indices)
    series_lines = [
        f"    {_series_call(chart.kind, one_series, xs, index, len(chart.series))},"
        for index, one_series in enumerate(chart.series)
    ]
    return "\n".join(
        [
            "#figure(",
            "  lq.diagram(",
            "    width: 12cm, height: 7cm,",
            f"    xlabel: [{escaped(chart.x_title or '')}], ylabel: [{escaped(chart.y_title or '')}],",
            f"    xaxis: (ticks: {ticks}, subticks: none),",
            *series_lines,
            "  ),",
            f"  caption: {_caption(caption)},",
            ")",
        ]
    )


def _series_call(
    kind: ChartKind, one_series: ChartSeries, xs: str, series_index: int, series_count: int
) -> str:
    values = _typst_array(_number(value) for value in one_series.values)
    label = f"label: [{escaped(one_series.name)}]"
    if kind is ChartKind.LINE:
        return f'lq.plot({xs}, {values}, mark: "o", {label})'
    bar_width = _BAR_GROUP_WIDTH / series_count
    offset = -_BAR_GROUP_WIDTH / 2 + bar_width * (series_index + 0.5)
    return f"lq.bar({xs}, {values}, width: {_number(bar_width)}, offset: {_number(offset)}, {label})"


def _number(value: float) -> str:
    formatted = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if formatted == "-0" else formatted


def _typst_array(items: Iterable[str]) -> str:
    return "(" + ", ".join(items) + ",)"


def _node_positions(diagram: DiagramData) -> Mapping[str, Position]:
    if diagram.kind is DiagramKind.FLOW:
        is_single_row = len(diagram.nodes) <= _FLOW_NODES_PER_ROW
        return {
            node.id: (index, 0) if is_single_row else (0, index)
            for index, node in enumerate(diagram.nodes)
        }
    return _hierarchy_positions(diagram)


def _hierarchy_positions(diagram: DiagramData) -> Mapping[str, Position]:
    """Tidy tree: leaves take consecutive columns in depth-first order, every
    parent sits centered above its own children, so sibling subtrees never
    overlap; nodes unreachable from a root line up on an extra bottom row."""
    tree = _HierarchyTree(diagram)
    positions: dict[str, Position] = {}
    next_column = 0.0
    for root in tree.roots:
        next_column = tree.place(root, 0, next_column, positions)
    unreached = [node.id for node in diagram.nodes if node.id not in positions]
    bottom_row = max((row for _, row in positions.values()), default=-1) + 1
    for node_id in unreached:
        positions[node_id] = (next_column, bottom_row)
        next_column += 1
    return positions


class _HierarchyTree:
    def __init__(self, diagram: DiagramData) -> None:
        self._children_by_id: dict[str, list[str]] = {node.id: [] for node in diagram.nodes}
        for edge in diagram.edges:
            self._children_by_id[edge.source].append(edge.target)
        targets = {edge.target for edge in diagram.edges}
        self.roots = [node.id for node in diagram.nodes if node.id not in targets] or [
            diagram.nodes[0].id
        ]
        self._visited: set[str] = set()
        self._level_by_id = self._levels()

    def place(
        self, node_id: str, row: int, next_column: float, positions: dict[str, Position]
    ) -> float:
        children = [
            child
            for child in self._children_by_id[node_id]
            if child not in self._visited and self._level_by_id[child] == row + 1
        ]
        self._visited.add(node_id)
        if not children:
            positions[node_id] = (next_column, row)
            return next_column + 1
        for child in children:
            next_column = self.place(child, row + 1, next_column, positions)
        child_columns = [positions[child][0] for child in children]
        positions[node_id] = ((child_columns[0] + child_columns[-1]) / 2, row)
        return next_column

    def _levels(self) -> dict[str, int]:
        level_by_id = {root: 0 for root in self.roots}
        queue = deque(self.roots)
        while queue:
            current = queue.popleft()
            for child in self._children_by_id[current]:
                if child not in level_by_id:
                    level_by_id[child] = level_by_id[current] + 1
                    queue.append(child)
        return level_by_id


def _point(position: Position) -> str:
    return f"({_number(position[0])}, {_number(position[1])})"


def _edge_label(label: str | None) -> str:
    if label is None:
        return ""
    return (
        f", label: text(size: 8pt, {_wrapped_text(label, _WRAPPED_EDGE_LABEL_WIDTH)}), "
        "label-side: center, label-fill: true"
    )


def _node_label(label: str) -> str:
    if len(label) <= _WRAP_LABELS_LONGER_THAN:
        return f"[{escaped(label)}]"
    return f"align(center, {_wrapped_text(label, _WRAPPED_LABEL_WIDTH)})"


def _wrapped_text(text: str, width: str) -> str:
    return f"box(width: {width}, par(justify: false)[{escaped(text)}])"


def _caption(caption: str) -> str:
    return f"[{escaped(caption)}]" if caption.strip() else "none"
