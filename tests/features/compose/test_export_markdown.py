# @covers output:CON-032
from pathlib import Path

import pytest

from konspekt.features.compose.application.compose_pdf import MissingFigureImageError
from konspekt.features.compose.application.export_markdown import export_markdown_bundle
from konspekt.features.compose.application.markdown_markup import MarkdownBundle


def a_bundle(image_paths: tuple[str, ...] = ("frames/f1.jpg",)) -> MarkdownBundle:
    return MarkdownBundle(
        files={
            "README.md": "# Лекция\n",
            "sections/01-s1.md": "# Раздел\n\n![c](images/f1.jpg)\n",
            "claims.md": "# Проверка фактов\n",
            "cut-log.md": "# Вырезанные фрагменты\n",
        },
        image_paths=image_paths,
        combined="# Всё в одном\n",
    )


def test_bundle_files_and_images_are_written_under_the_md_dir(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    (work_dir / "frames").mkdir(parents=True)
    (work_dir / "frames" / "f1.jpg").write_bytes(b"\xff\xd8jpg")
    md_dir = tmp_path / "md"

    readme_path = export_markdown_bundle(a_bundle(), md_dir, work_dir)

    assert readme_path == md_dir / "README.md"
    assert (md_dir / "sections" / "01-s1.md").read_text().startswith("# Раздел")
    assert (md_dir / "claims.md").exists() and (md_dir / "cut-log.md").exists()
    assert (md_dir / "images" / "f1.jpg").read_bytes() == b"\xff\xd8jpg"


def test_previous_bundle_is_replaced_not_merged(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    (work_dir / "frames").mkdir(parents=True)
    (work_dir / "frames" / "f1.jpg").write_bytes(b"jpg")
    md_dir = tmp_path / "md"
    (md_dir / "sections").mkdir(parents=True)
    stale = md_dir / "sections" / "09-old.md"
    stale.write_text("stale")

    export_markdown_bundle(a_bundle(), md_dir, work_dir)

    assert not stale.exists()


def test_missing_image_fails_naming_the_path(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    with pytest.raises(MissingFigureImageError, match="frames/f1.jpg"):
        export_markdown_bundle(a_bundle(), tmp_path / "md", work_dir)


# @covers output:DLT-034
def test_combined_document_is_written_next_to_the_md_dir(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    (work_dir / "frames").mkdir(parents=True)
    (work_dir / "frames" / "f1.jpg").write_bytes(b"jpg")
    bundle = MarkdownBundle(files=a_bundle().files, image_paths=("frames/f1.jpg",), combined="# Всё\n")

    export_markdown_bundle(bundle, tmp_path / "md", work_dir)

    assert (tmp_path / "konspekt.md").read_text() == "# Всё\n"
