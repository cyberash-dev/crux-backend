from pathlib import Path
from typing import Protocol


class PdfCompilerPort(Protocol):
    def compile(self, markup_path: Path, root_dir: Path, font_dirs: list[Path]) -> bytes: ...
