from dataclasses import dataclass
from enum import StrEnum

from konspekt.features.factcheck.domain.claims import Verdict
from konspekt.features.notes.domain.notes import BlockKind, BlockOrigin


class AdditionAction(StrEnum):
    KEPT = "kept"
    DROPPED = "dropped"
    KEPT_WITH_WARNING = "kept_with_warning"


@dataclass(frozen=True, slots=True)
class VerifiedAddition:
    """Audit record of one verified fact/definition block (analysis:REQ-028)."""

    text: str
    origin: BlockOrigin
    kind: BlockKind
    verdict: Verdict
    sources: tuple[str, ...]
    annotation: str | None
    action: AdditionAction

    def __post_init__(self) -> None:
        if self.kind not in (BlockKind.FACT, BlockKind.DEFINITION):
            raise ValueError("verified additions cover fact and definition blocks only")
