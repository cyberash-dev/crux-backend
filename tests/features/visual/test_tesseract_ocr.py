import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from konspekt.features.visual.adapters.outbound.tesseract_ocr import TesseractOcr


def has_rus_eng_traineddata() -> bool:
    if shutil.which("tesseract") is None:
        return False
    listed = subprocess.run(
        ["tesseract", "--list-langs"], capture_output=True, text=True
    )
    available_langs = listed.stdout.split()
    return "rus" in available_langs and "eng" in available_langs


def a_text_image(path: Path, text: str) -> Path:
    image = Image.new("L", (800, 200), color=255)
    drawing = ImageDraw.Draw(image)
    drawing.text((40, 60), text, fill=0, font=ImageFont.load_default(size=72))
    image.save(path)
    return path


@pytest.mark.skipif(
    not has_rus_eng_traineddata(),
    reason="tesseract with rus+eng traineddata is not available",
)
def test_reads_text_from_synthetic_image(tmp_path: Path) -> None:
    """# @covers extraction:EXT-004"""
    image_path = a_text_image(tmp_path / "slide.png", "KONSPEKT 42")

    ocr_text = TesseractOcr().read_text(image_path)

    assert ocr_text is not None
    assert "KONSPEKT" in ocr_text


def test_absent_binary_returns_none(tmp_path: Path) -> None:
    """# @covers extraction:EXT-004"""
    image_path = a_text_image(tmp_path / "slide.png", "KONSPEKT 42")

    ocr_text = TesseractOcr(binary_name="tesseract-binary-that-does-not-exist").read_text(
        image_path
    )

    assert ocr_text is None
