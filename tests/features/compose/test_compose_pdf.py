# @covers output:CON-030
# @covers output:EXT-020
# @covers output:CST-030
# @covers output:DLT-036
from pathlib import Path

import pytest
from PIL import Image

from konspekt.features.compose.adapters.outbound.typst_compiler import (
    TypstCompileError,
    TypstCompiler,
)
from konspekt.features.compose.application.compose_pdf import (
    MissingFigureImageError,
    compose_pdf,
)
from konspekt.features.notes.domain.notes import BlockKind, NoteBlock, NoteSection, Notes
from konspekt.shared.timecode import TimeRange
from tests.features.compose.metrics_fixture import a_metrics
from tests.features.compose.pdf_text_layer import extracted_text_variants, page_count

RU_PROBE = "Пример проверки конспекта № 1"
EN_PROBE = "Sample notes probe"
DEFINITION_TEXT_PROBE = "Структурированная запись лекции"
FACT_LABEL_PROBE = "Интересный факт"
EMPHASIZED_PROBE = "выделенный термин"
SUBSECTION_TITLE_PROBE = "Детали метода"


def bilingual_notes(figure_image_path: str) -> Notes:
    return Notes(
        title="Проверочная лекция",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Введение",
                source_spans=(TimeRange(0.0, 90.0),),
                blocks=(
                    NoteBlock(kind=BlockKind.PROSE, text=RU_PROBE),
                    NoteBlock(
                        kind=BlockKind.FIGURE,
                        image_path=figure_image_path,
                        caption="Схема с доски",
                        source_ref="video 00:00:42",
                    ),
                    NoteBlock(
                        kind=BlockKind.FACTCHECK_NOTE,
                        text="Утверждение подтверждено: https://example.org/source",
                        claim_ref=0,
                    ),
                    NoteBlock(
                        kind=BlockKind.DEFINITION,
                        term="Конспект",
                        text=DEFINITION_TEXT_PROBE,
                    ),
                    NoteBlock(
                        kind=BlockKind.FACT,
                        text="Первые конспекты появились в античности",
                    ),
                    NoteBlock(
                        kind=BlockKind.PROSE,
                        text=f"Дальше идёт **{EMPHASIZED_PROBE}** в абзаце",
                    ),
                ),
                subsections=(
                    NoteSection(
                        section_id="s1-1",
                        title=SUBSECTION_TITLE_PROBE,
                        source_spans=(TimeRange(30.0, 75.0),),
                        blocks=(
                            NoteBlock(kind=BlockKind.PROSE, text="Текст подсекции"),
                        ),
                    ),
                ),
            ),
            NoteSection(
                section_id="s2",
                title="English part",
                source_spans=(TimeRange(90.0, 180.0),),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text=EN_PROBE),),
            ),
        ),
    )



def a_work_dir_with_figure(tmp_path: Path) -> Path:
    figures_dir = tmp_path / "figures"
    figures_dir.mkdir()
    Image.new("RGB", (8, 8), color=(200, 40, 40)).save(figures_dir / "frame.png")
    return tmp_path


def composed_pdf_path(work_dir: Path) -> Path:
    return compose_pdf(
        notes=bilingual_notes("figures/frame.png"),
        video_file_name="lecture.mp4",
        generation_date="2026-08-19",
        work_dir=work_dir,
        compiler=TypstCompiler(),
        metrics=a_metrics(),
    )


def test_bilingual_fixture_compiles_to_valid_pdf(tmp_path: Path) -> None:
    work_dir = a_work_dir_with_figure(tmp_path)

    pdf_path = composed_pdf_path(work_dir)

    pdf_bytes = pdf_path.read_bytes()
    assert pdf_path.name == "konspekt.pdf"
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")
    assert page_count(pdf_bytes) >= 1
    assert (work_dir / "compose.typ").exists()


def test_compiled_pdf_text_layer_contains_both_probe_strings(tmp_path: Path) -> None:
    work_dir = a_work_dir_with_figure(tmp_path)

    pdf_bytes = composed_pdf_path(work_dir).read_bytes()

    variants = [variant.replace(" ", "") for variant in extracted_text_variants(pdf_bytes)]
    assert any(RU_PROBE.replace(" ", "") in variant for variant in variants)
    assert any(EN_PROBE.replace(" ", "") in variant for variant in variants)


def test_compiled_pdf_text_layer_contains_styled_block_content(tmp_path: Path) -> None:
    work_dir = a_work_dir_with_figure(tmp_path)

    pdf_bytes = composed_pdf_path(work_dir).read_bytes()

    variants = [variant.replace(" ", "") for variant in extracted_text_variants(pdf_bytes)]
    assert any(DEFINITION_TEXT_PROBE.replace(" ", "") in variant for variant in variants)
    assert any(FACT_LABEL_PROBE.replace(" ", "") in variant for variant in variants)
    assert any(EMPHASIZED_PROBE.replace(" ", "") in variant for variant in variants)
    assert (work_dir / "compose.typ").read_text(encoding="utf-8").count("**") == 0


def test_compiled_pdf_text_layer_contains_subsection_title(tmp_path: Path) -> None:
    work_dir = a_work_dir_with_figure(tmp_path)

    pdf_bytes = composed_pdf_path(work_dir).read_bytes()

    variants = [variant.replace(" ", "") for variant in extracted_text_variants(pdf_bytes)]
    assert any(SUBSECTION_TITLE_PROBE.replace(" ", "") in variant for variant in variants)


def test_compiled_pdf_carries_no_quiz_content(tmp_path: Path) -> None:
    work_dir = a_work_dir_with_figure(tmp_path)

    pdf_bytes = composed_pdf_path(work_dir).read_bytes()

    markup = (work_dir / "compose.typ").read_text(encoding="utf-8")
    assert "Тест для самопроверки" not in markup
    assert "Ключ ответов" not in markup
    variants = [variant.replace(" ", "") for variant in extracted_text_variants(pdf_bytes)]
    assert all("Тестдлясамопроверки" not in variant for variant in variants)
    assert all("Ключответов" not in variant for variant in variants)


def test_markup_syntax_error_raises_typed_error_with_diagnostics(tmp_path: Path) -> None:
    broken_markup_path = tmp_path / "broken.typ"
    broken_markup_path.write_text("#nonexistent_function(", encoding="utf-8")
    compiler = TypstCompiler()

    with pytest.raises(TypstCompileError, match="nonexistent_function|unclosed|expected"):
        compiler.compile(broken_markup_path, tmp_path, [])


class RecordingCompiler:
    def __init__(self) -> None:
        self.was_called = False

    def compile(self, markup_path: Path, root_dir: Path, font_dirs: list[Path]) -> bytes:
        self.was_called = True
        return b"%PDF-fake"


def test_missing_figure_image_raises_error_naming_path_before_compilation(
    tmp_path: Path,
) -> None:
    compiler = RecordingCompiler()

    with pytest.raises(MissingFigureImageError, match="figures/absent.png"):
        compose_pdf(
            notes=bilingual_notes("figures/absent.png"),
            video_file_name="lecture.mp4",
            generation_date="2026-08-19",
            work_dir=tmp_path,
            compiler=compiler,
            metrics=a_metrics(),
        )

    assert compiler.was_called is False


def test_compiled_pdf_text_layer_contains_evidence_summary(tmp_path: Path) -> None:
    work_dir = a_work_dir_with_figure(tmp_path)

    pdf_bytes = composed_pdf_path(work_dir).read_bytes()

    variants = [variant.replace(" ", "") for variant in extracted_text_variants(pdf_bytes)]
    assert any("Покрытиетаймлайна" in variant for variant in variants)
    assert any("96.1%" in variant for variant in variants)
