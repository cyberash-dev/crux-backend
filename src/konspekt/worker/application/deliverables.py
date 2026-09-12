import mimetypes
from pathlib import Path

from konspekt.worker.domain.deliverable import Deliverable
from konspekt.worker.domain.file_kind import FileKind

_PDF_NAME = "konspekt.pdf"
_MARKDOWN_NAME = "konspekt.md"
_IMAGES_DIR = Path("md", "images")


def deliverables(lecture_dir: Path) -> list[Deliverable]:
    image_paths = sorted(
        path for path in (lecture_dir / _IMAGES_DIR).iterdir() if path.is_file()
    )
    return [
        Deliverable(FileKind.PDF, _PDF_NAME, lecture_dir / _PDF_NAME, "application/pdf"),
        Deliverable(
            FileKind.MARKDOWN, _MARKDOWN_NAME, lecture_dir / _MARKDOWN_NAME, "text/markdown"
        ),
        *(
            Deliverable(
                FileKind.IMAGE,
                (_IMAGES_DIR / image_path.name).as_posix(),
                image_path,
                _image_content_type(image_path),
            )
            for image_path in image_paths
        ),
    ]


def _image_content_type(image_path: Path) -> str:
    content_type, _ = mimetypes.guess_type(image_path.name)
    if content_type is None or not content_type.startswith("image/"):
        raise ValueError(f"no image content type for {image_path.name}")
    return content_type
