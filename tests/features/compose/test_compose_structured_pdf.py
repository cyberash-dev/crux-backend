# @covers output:CON-030
# @covers output:DLT-033
# @covers output:EXT-021
from pathlib import Path

import pytest

from konspekt.features.compose.adapters.outbound.typst_compiler import TypstCompiler
from konspekt.features.compose.application.compose_pdf import compose_pdf
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
from tests.features.compose.metrics_fixture import a_metrics
from tests.features.compose.pdf_text_layer import extracted_text_variants, page_count

TABLE_CELL_PROBES = ("Быстраясортировка", "Пузырьковая", "340")


def structured_notes() -> Notes:
    return Notes(
        title="Лекция со структурными блоками",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Структуры",
                source_spans=(TimeRange(0.0, 90.0),),
                blocks=(
                    NoteBlock(
                        kind=BlockKind.TABLE,
                        caption="Сравнение методов",
                        table=TableData(
                            columns=("Метод", "Скорость, мс"),
                            rows=(("Быстрая сортировка", "12"), ("Пузырьковая", "340")),
                        ),
                    ),
                    NoteBlock(
                        kind=BlockKind.DIAGRAM,
                        caption="Классификация",
                        diagram=DiagramData(
                            kind=DiagramKind.HIERARCHY,
                            nodes=(
                                DiagramNode("root", "Алгоритмы"),
                                DiagramNode("a", "Сортировка"),
                                DiagramNode("b", "Поиск"),
                            ),
                            edges=(DiagramEdge("root", "a"), DiagramEdge("root", "b", "да")),
                        ),
                    ),
                    NoteBlock(
                        kind=BlockKind.DIAGRAM,
                        caption="Процесс",
                        diagram=DiagramData(
                            kind=DiagramKind.FLOW,
                            nodes=tuple(
                                DiagramNode(f"n{index}", f"Шаг {index}") for index in range(5)
                            ),
                            edges=tuple(
                                DiagramEdge(f"n{index}", f"n{index + 1}") for index in range(4)
                            ),
                        ),
                    ),
                    NoteBlock(
                        kind=BlockKind.CHART,
                        caption="Выручка по годам",
                        chart=ChartData(
                            kind=ChartKind.BAR,
                            categories=("2020", "2021", "2022"),
                            series=(
                                ChartSeries("Продажи", (5.0, 3.0, 8.0)),
                                ChartSeries("Возвраты", (1.0, 2.5, 1.5)),
                            ),
                            x_title="Год",
                            y_title="Млн руб.",
                        ),
                    ),
                    NoteBlock(
                        kind=BlockKind.CHART,
                        caption="Температура",
                        chart=ChartData(
                            kind=ChartKind.LINE,
                            categories=("Янв", "Фев", "Мар"),
                            series=(ChartSeries("Москва", (-8.0, -6.5, 0.0)),),
                            x_title="Месяц",
                            y_title="°C",
                        ),
                    ),
                ),
            ),
        ),
    )


def composed_structured_pdf_bytes(work_dir: Path) -> bytes:
    pdf_path = compose_pdf(
        notes=structured_notes(),
        video_file_name="lecture.mp4",
        generation_date="2026-08-22",
        work_dir=work_dir,
        compiler=TypstCompiler(),
        metrics=a_metrics(),
    )
    return pdf_path.read_bytes()


def test_structured_blocks_fixture_compiles_to_non_empty_pdf(tmp_path: Path) -> None:
    pdf_bytes = composed_structured_pdf_bytes(tmp_path)

    assert pdf_bytes.startswith(b"%PDF")
    assert page_count(pdf_bytes) >= 1


@pytest.mark.parametrize("cell_probe", TABLE_CELL_PROBES)
def test_compiled_pdf_text_layer_contains_table_cell_string(
    tmp_path: Path, cell_probe: str
) -> None:
    pdf_bytes = composed_structured_pdf_bytes(tmp_path)

    variants = [variant.replace(" ", "") for variant in extracted_text_variants(pdf_bytes)]
    assert any(cell_probe in variant for variant in variants)
