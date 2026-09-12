from konspekt.features.compose.application.metrics import LectureMetrics


def a_metrics() -> LectureMetrics:
    return LectureMetrics(
        source_duration_seconds=5025.0,
        accounted_duration_seconds=4830.0,
        included_duration_seconds=4200.0,
        cut_duration_seconds=630.0,
        section_count=3,
        subsection_count=2,
        figure_count=2,
        table_count=1,
        diagram_count=1,
        chart_count=0,
        claims_checked=5,
        claims_disputed=1,
        claims_mixed=1,
        model_added_verified=0,
        question_count=8,
    )
