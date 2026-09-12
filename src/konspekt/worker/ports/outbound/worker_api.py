from collections.abc import Mapping, Sequence
from typing import Protocol

from konspekt.worker.domain.failure_code import FailureCode
from konspekt.worker.domain.stored_file import StoredFile


class WorkerApiPort(Protocol):
    def report_heartbeat(self) -> None: ...

    def report_stage_completed(self, stage: str) -> None: ...

    def upload(self, name: str, content_type: str, content: bytes) -> str:
        """Stores the file in the control plane and returns its storage id."""
        ...

    def complete_succeeded(
        self, result: Mapping[str, object], files: Sequence[StoredFile]
    ) -> None: ...

    def complete_failed(self, code: FailureCode, message: str) -> None: ...
