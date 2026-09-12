# @covers output:CON-030
# @covers output:DLT-033
import pytest

from konspekt.features.compose.application.typst_markup import render_markup
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
    NoteSection,
    Notes,
    TableData,
)
from konspekt.shared.timecode import TimeRange
from tests.features.compose.metrics_fixture import a_metrics

GENERATED_LABELS = {
    "ru": "Иллюстрация сгенерирована ИИ",
    "en": "AI-generated illustration",
}


def notes_with_block(block: NoteBlock, language: str = "ru") -> Notes:
    return Notes(
        title="Лекция",
        language=language,
        sections=(
            NoteSection(
                section_id="s1",
                title="Введение",
                source_spans=(TimeRange(0.0, 10.0),),
                blocks=(block,),
            ),
        ),
    )


def a_figure(source_ref: str, provenance: FigureProvenance | None = None) -> NoteBlock:
    return NoteBlock(
        kind=BlockKind.FIGURE,
        image_path="figures/frame.png",
        caption="Иллюстрация",
        source_ref=source_ref,
        provenance=provenance,
    )


@pytest.mark.parametrize("language", ["ru", "en"])
def test_generated_figure_attribution_carries_ai_label(language: str) -> None:
    notes = notes_with_block(a_figure("generated:codex"), language)

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert f"generated:codex · {GENERATED_LABELS[language]}" in markup


@pytest.mark.parametrize("language", ["ru", "en"])
def test_video_frame_figure_attribution_carries_no_ai_label(language: str) -> None:
    notes = notes_with_block(a_figure("video 00:00:05"), language)

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert GENERATED_LABELS[language] not in markup


def a_table_block() -> NoteBlock:
    return NoteBlock(
        kind=BlockKind.TABLE,
        caption="Сравнение #методов",
        table=TableData(
            columns=("Метод", "Скорость [мс]"),
            rows=(("Быстрая *сортировка*", "12"), ("Пузырьковая", "340")),
        ),
    )


def test_table_markup_renders_header_cells_bold() -> None:
    notes = notes_with_block(a_table_block())

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "table.header([*Метод*], [*Скорость \\[мс\\]*])" in markup


def test_table_markup_escapes_every_cell_string() -> None:
    notes = notes_with_block(a_table_block())

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "[Быстрая \\*сортировка\\*], [12]" in markup
    assert "[Пузырьковая], [340]" in markup
    assert "caption: [Сравнение \\#методов]" in markup


def test_table_markup_declares_one_column_per_table_column() -> None:
    notes = notes_with_block(a_table_block())

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "table(columns: 2," in markup


def a_hierarchy_diagram_block() -> NoteBlock:
    return NoteBlock(
        kind=BlockKind.DIAGRAM,
        caption="Классификация",
        diagram=DiagramData(
            kind=DiagramKind.HIERARCHY,
            nodes=(
                DiagramNode("root", "Корень"),
                DiagramNode("a", "Ветвь A"),
                DiagramNode("b", "Ветвь B"),
                DiagramNode("leaf", "Лист"),
            ),
            edges=(
                DiagramEdge("root", "a"),
                DiagramEdge("root", "b", label="да"),
                DiagramEdge("a", "leaf"),
            ),
        ),
    )


def a_flow_diagram_block(node_count: int = 3) -> NoteBlock:
    nodes = tuple(DiagramNode(f"n{index}", f"Шаг {index}") for index in range(node_count))
    edges = tuple(
        DiagramEdge(f"n{index}", f"n{index + 1}") for index in range(node_count - 1)
    )
    return NoteBlock(
        kind=BlockKind.DIAGRAM,
        caption="Процесс",
        diagram=DiagramData(kind=DiagramKind.FLOW, nodes=nodes, edges=edges),
    )


def test_hierarchy_diagram_places_children_on_row_below_parent() -> None:
    notes = notes_with_block(a_hierarchy_diagram_block())

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "node((0.5, 0), [Корень])" in markup
    assert "node((0, 1), [Ветвь A])" in markup
    assert "node((1, 1), [Ветвь B])" in markup
    assert "node((0, 2), [Лист])" in markup


def test_parent_is_centered_over_its_children_without_crossing_other_subtrees() -> None:
    diagram = DiagramData(
        kind=DiagramKind.HIERARCHY,
        nodes=(
            DiagramNode("root", "Корень"),
            DiagramNode("a", "А"),
            DiagramNode("b", "Б"),
            DiagramNode("a1", "А1"),
            DiagramNode("a2", "А2"),
            DiagramNode("b1", "Б1"),
        ),
        edges=(
            DiagramEdge("root", "a"),
            DiagramEdge("root", "b"),
            DiagramEdge("a", "a1"),
            DiagramEdge("a", "a2"),
            DiagramEdge("b", "b1"),
        ),
    )
    notes = notes_with_block(
        NoteBlock(kind=BlockKind.DIAGRAM, caption="Дерево", diagram=diagram)
    )

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "node((0, 2), [А1])" in markup
    assert "node((1, 2), [А2])" in markup
    assert "node((2, 2), [Б1])" in markup
    assert "node((0.5, 1), [А])" in markup
    assert "node((2, 1), [Б])" in markup
    assert "node((1.25, 0), [Корень])" in markup


def test_diagram_is_scaled_down_to_the_available_width() -> None:
    notes = notes_with_block(a_hierarchy_diagram_block())

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "layout(size =>" in markup
    assert "scale(" in markup and "reflow: true" in markup


def test_flow_diagram_chains_nodes_left_to_right() -> None:
    notes = notes_with_block(a_flow_diagram_block(3))

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "node((0, 0), [Шаг 0])" in markup
    assert "node((1, 0), [Шаг 1])" in markup
    assert "node((2, 0), [Шаг 2])" in markup


def test_long_flow_diagram_runs_top_down_instead_of_wrapping() -> None:
    notes = notes_with_block(a_flow_diagram_block(5))

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "node((0, 0), [Шаг 0])" in markup
    assert "node((0, 3), [Шаг 3])" in markup
    assert "node((0, 4), [Шаг 4])" in markup


def test_diagram_markup_draws_one_arrow_per_declared_edge() -> None:
    notes = notes_with_block(a_hierarchy_diagram_block())

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert 'edge((0.5, 0), (0, 1), "-|>")' in markup
    assert (
        'edge((0.5, 0), (1, 1), "-|>", label: text(size: 8pt, box(width: 7em, '
        "par(justify: false)[да])), label-side: center, label-fill: true)" in markup
    )
    assert 'edge((0, 1), (0, 2), "-|>")' in markup
    assert markup.count("edge(") == 3


def test_diagram_markup_wraps_drawing_in_captioned_figure() -> None:
    notes = notes_with_block(a_hierarchy_diagram_block())

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "#figure(\n  layout(size => {\n    let drawing = diagram(" in markup
    assert "caption: [Классификация]" in markup


def test_fletcher_import_is_emitted_only_when_a_diagram_block_exists() -> None:
    with_diagram = notes_with_block(a_flow_diagram_block())
    without_diagram = notes_with_block(a_table_block())

    markup_with = render_markup(with_diagram, "lecture.mp4", "2026-08-22", a_metrics())
    markup_without = render_markup(without_diagram, "lecture.mp4", "2026-08-22", a_metrics())

    assert '#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge' in markup_with
    assert "fletcher" not in markup_without


def a_chart_block(kind: ChartKind) -> NoteBlock:
    return NoteBlock(
        kind=BlockKind.CHART,
        caption="Рост выручки",
        chart=ChartData(
            kind=kind,
            categories=("2020", "2021 [план]"),
            series=(
                ChartSeries("Продажи", (5.0, 3.5)),
                ChartSeries("Возвраты #2", (1.0, 2.25)),
            ),
            x_title="Год",
            y_title="Млн $",
        ),
    )


@pytest.mark.parametrize("kind", [ChartKind.BAR, ChartKind.LINE])
def test_chart_markup_carries_category_tick_labels(kind: ChartKind) -> None:
    notes = notes_with_block(a_chart_block(kind))

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "xaxis: (ticks: ((0, [2020]), (1, [2021 \\[план\\]]),), subticks: none)" in markup


@pytest.mark.parametrize("kind", [ChartKind.BAR, ChartKind.LINE])
def test_chart_markup_carries_escaped_axis_titles(kind: ChartKind) -> None:
    notes = notes_with_block(a_chart_block(kind))

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "xlabel: [Год]" in markup
    assert "ylabel: [Млн \\$]" in markup


def test_bar_chart_markup_emits_one_offset_bar_call_per_series() -> None:
    notes = notes_with_block(a_chart_block(ChartKind.BAR))

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "lq.bar((0, 1,), (5, 3.5,), width: 0.4, offset: -0.2, label: [Продажи])" in markup
    assert "lq.bar((0, 1,), (1, 2.25,), width: 0.4, offset: 0.2, label: [Возвраты \\#2])" in markup
    assert markup.count("lq.bar(") == 2
    assert "lq.plot(" not in markup


def test_line_chart_markup_emits_one_plot_call_per_series() -> None:
    notes = notes_with_block(a_chart_block(ChartKind.LINE))

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert 'lq.plot((0, 1,), (5, 3.5,), mark: "o", label: [Продажи])' in markup
    assert 'lq.plot((0, 1,), (1, 2.25,), mark: "o", label: [Возвраты \\#2])' in markup
    assert markup.count("lq.plot(") == 2
    assert "lq.bar(" not in markup


def test_chart_markup_wraps_diagram_in_captioned_figure() -> None:
    notes = notes_with_block(a_chart_block(ChartKind.BAR))

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "#figure(\n  lq.diagram(" in markup
    assert "caption: [Рост выручки]" in markup


def test_lilaq_import_is_emitted_only_when_a_chart_block_exists() -> None:
    with_chart = notes_with_block(a_chart_block(ChartKind.LINE))
    without_chart = notes_with_block(a_flow_diagram_block())

    markup_with = render_markup(with_chart, "lecture.mp4", "2026-08-22", a_metrics())
    markup_without = render_markup(without_chart, "lecture.mp4", "2026-08-22", a_metrics())

    assert '#import "@preview/lilaq:0.5.0" as lq' in markup_with
    assert "lilaq" not in markup_without


def test_table_figures_are_allowed_to_break_across_pages() -> None:
    notes = notes_with_block(a_table_block())

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "#show figure.where(kind: table): set block(breakable: true)" in markup


def test_hierarchy_diagram_without_roots_starts_from_first_node() -> None:
    cyclic = NoteBlock(
        kind=BlockKind.DIAGRAM,
        caption="Цикл",
        diagram=DiagramData(
            kind=DiagramKind.HIERARCHY,
            nodes=(DiagramNode("a", "А"), DiagramNode("b", "Б")),
            edges=(DiagramEdge("a", "b"), DiagramEdge("b", "a")),
        ),
    )
    notes = notes_with_block(cyclic)

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "node((0, 0), [А])" in markup
    assert "node((0, 1), [Б])" in markup


def test_long_node_labels_wrap_inside_a_fixed_width_box() -> None:
    diagram = DiagramData(
        kind=DiagramKind.FLOW,
        nodes=(
            DiagramNode("a", "Коротко"),
            DiagramNode("b", "Очень длинная подпись узла схемы"),
        ),
        edges=(DiagramEdge("a", "b"),),
    )
    notes = notes_with_block(NoteBlock(kind=BlockKind.DIAGRAM, caption="c", diagram=diagram))

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert "node((0, 0), [Коротко])" in markup
    assert (
        "node((1, 0), align(center, box(width: 8em, par(justify: false)"
        "[Очень длинная подпись узла схемы])))" in markup
    )


def test_structured_block_without_caption_renders_no_caption_label() -> None:
    block = NoteBlock(
        kind=BlockKind.TABLE,
        caption=None,
        table=TableData(columns=("a",), rows=(("1",),)),
    )

    markup = render_markup(notes_with_block(block), "lecture.mp4", "2026-08-22", a_metrics())

    assert "caption: none" in markup
    assert "caption: []" not in markup


def test_table_cells_are_not_justified() -> None:
    markup = render_markup(notes_with_block(a_table_block()), "lecture.mp4", "2026-08-22", a_metrics())

    assert "#show table: set par(justify: false)" in markup
