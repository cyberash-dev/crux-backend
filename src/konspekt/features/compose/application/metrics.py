from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LectureMetrics:
    """Deterministic evidence summary computed from the artifacts
    (output:DLT-036/DLT-037); never produced by an LLM."""

    source_duration_seconds: float
    accounted_duration_seconds: float
    included_duration_seconds: float
    cut_duration_seconds: float
    section_count: int
    subsection_count: int
    figure_count: int
    table_count: int
    diagram_count: int
    chart_count: int
    claims_checked: int
    claims_disputed: int
    claims_mixed: int
    model_added_verified: int
    question_count: int

    @property
    def coverage_ratio(self) -> float:
        if self.source_duration_seconds <= 0:
            return 0.0
        return self.accounted_duration_seconds / self.source_duration_seconds
