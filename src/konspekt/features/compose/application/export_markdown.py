import shutil
from pathlib import Path

from konspekt.features.compose.application.compose_pdf import MissingFigureImageError
from konspekt.features.compose.application.markdown_markup import (
    COMBINED_FILE_NAME,
    IMAGES_DIR_NAME,
    README_FILE_NAME,
    MarkdownBundle,
)


def export_markdown_bundle(bundle: MarkdownBundle, md_dir: Path, work_dir: Path) -> Path:
    source_images = [(image_path, work_dir / image_path) for image_path in bundle.image_paths]
    for image_path, source in source_images:
        if not source.is_file():
            raise MissingFigureImageError(image_path)
    if md_dir.exists():
        shutil.rmtree(md_dir)
    for relative_path, content in bundle.files.items():
        target = md_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    images_dir = md_dir / IMAGES_DIR_NAME
    images_dir.mkdir(parents=True, exist_ok=True)
    for _, source in source_images:
        shutil.copyfile(source, images_dir / source.name)
    (md_dir.parent / COMBINED_FILE_NAME).write_text(bundle.combined, encoding="utf-8")
    return md_dir / README_FILE_NAME
