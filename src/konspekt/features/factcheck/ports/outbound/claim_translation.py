from collections.abc import Sequence
from typing import Protocol


class ClaimTranslationPort(Protocol):
    def english_queries(self, claim_texts: Sequence[str], language: str) -> list[str]: ...
