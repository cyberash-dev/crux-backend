# @covers output:DLT-036
# @covers output:DLT-037
from konspekt.features.factcheck.domain.claims import CheckedClaim, Verdict
from konspekt.features.notes.domain.audit import AdditionAction, VerifiedAddition
from konspekt.features.notes.domain.notes import (
    BlockKind,
    BlockOrigin,
    NoteBlock,
    NoteSection,
    Notes,
    TableData,
)
from konspekt.features.quiz.domain.quiz import Quiz
from konspekt.features.segmentation.domain.segments import LabeledSpan, SpanLabel
from konspekt.pipeline.lecture_metrics import build_lecture_metrics
from konspekt.shared.timecode import TimeRange


def a_span(start: float, end: float, label: SpanLabel) -> LabeledSpan:
    section_id = "s1" if label is SpanLabel.CORE else None
    reason = None if label is SpanLabel.CORE else "r"
    return LabeledSpan(TimeRange(start, end), label, section_id, reason)


def a_claim(verdict: Verdict) -> CheckedClaim:
    sources = () if verdict is Verdict.UNVERIFIED else ("https://x",)
    annotation = "a" if verdict in (Verdict.DISPUTED, Verdict.MIXED) else None
    return CheckedClaim("t", TimeRange(0.0, 1.0), verdict, sources, annotation)


def an_addition(origin: BlockOrigin) -> VerifiedAddition:
    return VerifiedAddition(
        text="f",
        origin=origin,
        kind=BlockKind.FACT,
        verdict=Verdict.CONFIRMED,
        sources=("https://x",),
        annotation=None,
        action=AdditionAction.KEPT,
    )


def test_model_added_verified_counts_only_model_added_rows() -> None:
    """# @covers output:DLT-036"""
    additions = (
        an_addition(BlockOrigin.LECTURE),
        an_addition(BlockOrigin.MODEL_ADDED),
        an_addition(BlockOrigin.LECTURE),
    )

    metrics = build_lecture_metrics(
        duration_seconds=0.0,
        spans=[],
        notes=Notes(title="t", language="ru", sections=()),
        claims=[],
        verified_additions=additions,
        quiz=Quiz(questions=()),
    )

    assert metrics.model_added_verified == 1


def test_metrics_are_derived_from_artifacts_deterministically() -> None:
    notes = Notes(
        title="t",
        language="ru",
        sections=(
            NoteSection(
                "s1",
                "S1",
                (TimeRange(0.0, 600.0),),
                (
                    NoteBlock(kind=BlockKind.PROSE, text="p"),
                    NoteBlock(
                        kind=BlockKind.FIGURE,
                        image_path="f.jpg",
                        source_ref="video 00:00:01",
                    ),
                    NoteBlock(
                        kind=BlockKind.TABLE,
                        table=TableData(("a",), (("1",),)),
                    ),
                ),
                subsections=(
                    NoteSection(
                        "s1.1",
                        "S11",
                        (TimeRange(0.0, 300.0),),
                        (NoteBlock(kind=BlockKind.PROSE, text="p2"),),
                    ),
                ),
            ),
        ),
    )
    spans = [
        a_span(0.0, 700.0, SpanLabel.CORE),
        a_span(700.0, 800.0, SpanLabel.ANECDOTE),
    ]
    claims = [a_claim(Verdict.CONFIRMED), a_claim(Verdict.DISPUTED), a_claim(Verdict.MIXED)]
    additions = (
        VerifiedAddition(
            text="f",
            origin=BlockOrigin.MODEL_ADDED,
            kind=BlockKind.FACT,
            verdict=Verdict.CONFIRMED,
            sources=("https://x",),
            annotation=None,
            action=AdditionAction.KEPT,
        ),
    )
    quiz = Quiz(questions=())

    metrics = build_lecture_metrics(
        duration_seconds=800.0,
        spans=spans,
        notes=notes,
        claims=claims,
        verified_additions=additions,
        quiz=quiz,
    )

    assert metrics.source_duration_seconds == 800.0
    assert metrics.accounted_duration_seconds == 800.0
    assert metrics.included_duration_seconds == 700.0
    assert metrics.cut_duration_seconds == 100.0
    assert metrics.coverage_ratio == 1.0
    assert (metrics.section_count, metrics.subsection_count) == (1, 1)
    assert (metrics.figure_count, metrics.table_count) == (1, 1)
    assert (metrics.diagram_count, metrics.chart_count) == (0, 0)
    assert metrics.claims_checked == 3
    assert (metrics.claims_disputed, metrics.claims_mixed) == (1, 1)
    assert metrics.model_added_verified == 1
    assert metrics.question_count == 0
