from dataclasses import dataclass

from konspekt.worker.domain.file_kind import FileKind


@dataclass(frozen=True, slots=True)
class StoredFile:
    kind: FileKind
    name: str
    storage_id: str
    size_bytes: int
    content_type: str
