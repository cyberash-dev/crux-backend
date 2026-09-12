from typing import Protocol

from konspekt.features.factcheck.domain.evidence import Evidence


class EvidenceSearchPort(Protocol):
    def search(self, query: str) -> list[Evidence]: ...
