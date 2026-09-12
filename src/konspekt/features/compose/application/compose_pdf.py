from pathlib import Path

from konspekt.features.compose.application.metrics import LectureMetrics
from konspekt.features.compose.application.typst_markup import render_markup
from konspekt.features.compose.ports.outbound.pdf_compiler import PdfCompilerPort
from konspekt.features.notes.domain.notes import BlockKind, Notes

MARKUP_FILE_NAME = "compose.typ"
PDF_FILE_NAME = "konspekt.pdf"

_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


class MissingFigureImageError(Exception):
    def __init__(self, image_path: str) -> None:
        super().__init__(f"figure image file not found: {image_path}")
        self.image_path = image_path


def compose_pdf(
    notes: Notes,
    video_file_name: str,
    generation_date: str,
    work_dir: Path,
    compiler: PdfCompilerPort,
    metrics: LectureMetrics,
) -> Path:
    _ensure_figure_images_exist(notes, work_dir)
    markup = render_markup(notes, video_file_name, generation_date, metrics)
    markup_path = work_dir / MARKUP_FILE_NAME
    markup_path.write_text(markup, encoding="utf-8")
    pdf_bytes = compiler.compile(markup_path, work_dir, [_FONTS_DIR])
    pdf_path = work_dir / PDF_FILE_NAME
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path


def _ensure_figure_images_exist(notes: Notes, work_dir: Path) -> None:
    for section in notes.sections:
        for block in section.blocks:
            if block.kind is BlockKind.FIGURE and block.image_path is not None:
                if not (work_dir / block.image_path).exists():
                    raise MissingFigureImageError(block.image_path)
