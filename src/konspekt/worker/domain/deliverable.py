from dataclasses import dataclass
from pathlib import Path

from konspekt.worker.domain.file_kind import FileKind


@dataclass(frozen=True, slots=True)
class Deliverable:
    kind: FileKind
    name: str
    path: Path
    content_type: str
