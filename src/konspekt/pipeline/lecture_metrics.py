from collections.abc import Sequence

from konspekt.features.compose.application.metrics import LectureMetrics
from konspekt.features.factcheck.domain.claims import CheckedClaim, Verdict
from konspekt.features.notes.domain.audit import VerifiedAddition
from konspekt.features.notes.domain.notes import BlockKind, BlockOrigin, Notes
from konspekt.features.quiz.domain.quiz import Quiz
from konspekt.features.segmentation.domain.segments import LabeledSpan, SpanLabel


def build_lecture_metrics(
    duration_seconds: float,
    spans: Sequence[LabeledSpan],
    notes: Notes,
    claims: Sequence[CheckedClaim],
    verified_additions: Sequence[VerifiedAddition],
    quiz: Quiz,
) -> LectureMetrics:
    included_seconds = _total_duration(spans, {SpanLabel.CORE})
    cut_seconds = _total_duration(
        spans, {SpanLabel.TANGENT, SpanLabel.ANECDOTE, SpanLabel.ADMIN}
    )
    block_counts = _block_counts(notes)
    return LectureMetrics(
        source_duration_seconds=duration_seconds,
        accounted_duration_seconds=included_seconds + cut_seconds,
        included_duration_seconds=included_seconds,
        cut_duration_seconds=cut_seconds,
        section_count=len(notes.sections),
        subsection_count=len(notes.all_sections()) - len(notes.sections),
        figure_count=block_counts[BlockKind.FIGURE],
        table_count=block_counts[BlockKind.TABLE],
        diagram_count=block_counts[BlockKind.DIAGRAM],
        chart_count=block_counts[BlockKind.CHART],
        claims_checked=len(claims),
        claims_disputed=sum(1 for claim in claims if claim.verdict is Verdict.DISPUTED),
        claims_mixed=sum(1 for claim in claims if claim.verdict is Verdict.MIXED),
        model_added_verified=sum(
            1 for addition in verified_additions if addition.origin is BlockOrigin.MODEL_ADDED
        ),
        question_count=len(quiz.questions),
    )


def _total_duration(spans: Sequence[LabeledSpan], labels: set[SpanLabel]) -> float:
    return sum(
        span.time_range.end_seconds - span.time_range.start_seconds
        for span in spans
        if span.label in labels
    )


def _block_counts(notes: Notes) -> dict[BlockKind, int]:
    counts = {kind: 0 for kind in BlockKind}
    for section in notes.all_sections():
        for block in section.blocks:
            counts[block.kind] += 1
    return counts
