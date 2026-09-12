# @covers output:CST-030
from pathlib import Path

FONTS_DIR = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "konspekt"
    / "features"
    / "compose"
    / "assets"
    / "fonts"
)


def test_bundled_fonts_directory_contains_noto_family() -> None:
    ttf_files = sorted(path.name for path in FONTS_DIR.glob("*.ttf"))

    assert len(ttf_files) >= 4
    assert "NotoSans-Regular.ttf" in ttf_files
    assert "NotoSans-Bold.ttf" in ttf_files
    assert "NotoSans-Italic.ttf" in ttf_files
    assert "NotoSansMono-Regular.ttf" in ttf_files


def test_bundled_fonts_directory_contains_ofl_license() -> None:
    license_path = FONTS_DIR / "OFL.txt"

    license_text = license_path.read_text(encoding="utf-8")

    assert "SIL OPEN FONT LICENSE" in license_text
