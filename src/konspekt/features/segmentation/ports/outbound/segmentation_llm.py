from typing import Protocol

from konspekt.features.segmentation.domain.segments import (
    LabeledSpan,
    SectionPlanEntry,
)
from konspekt.features.transcription.domain.transcript import Transcript


class SegmentationLlmPort(Protocol):
    def plan_outline(self, transcript: Transcript) -> tuple[str, list[SectionPlanEntry]]:
        """Returns (lecture_title, hierarchical sections plan)."""
        ...

    def label_spans(
        self, transcript: Transcript, sections_plan: list[SectionPlanEntry]
    ) -> list[LabeledSpan]: ...
