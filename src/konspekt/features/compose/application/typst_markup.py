from collections.abc import Mapping

from konspekt.features.compose.application.structured_markup import (
    FLETCHER_IMPORT,
    LILAQ_IMPORT,
    chart_markup,
    diagram_markup,
    table_markup,
)
from konspekt.features.compose.application.metrics import LectureMetrics
from konspekt.features.compose.application.metrics_text import (
    coverage_percent_label,
    duration_label,
)
from konspekt.features.compose.application.typst_text import escaped, string_literal
from konspekt.features.compose.application.labels import labels_for
from konspekt.features.factcheck.domain.claims import Verdict
from konspekt.features.notes.domain.notes import (
    BlockKind,
    FigureProvenance,
    NoteBlock,
    NoteSection,
    Notes,
)
from konspekt.shared.timecode import TimeRange

_EMPHASIS_MARKER = "**"
MAX_FIGURE_HEIGHT = "11cm"

DEFINITION_FILL = "#eef4fb"
_DEFINITION_STRIPE = "#1a5fb4"
FACT_FILL = "#e9f7ef"
_FACT_STRIPE = "#2e8b57"
FACTCHECK_FILL = "#fff3cd"
_FACTCHECK_STRIPE = "#e0a800"
_EMPHASIS_TINT = "#1a5fb4"

def render_markup(
    notes: Notes,
    video_file_name: str,
    generation_date: str,
    metrics: LectureMetrics,
) -> str:
    headings = labels_for(notes.language)
    chapters = [_section_chapter(section, headings) for section in notes.sections]
    return "\n".join(
        [
            _preamble(notes.language),
            *_package_imports(notes),
            _title_page(notes.title, video_file_name, generation_date, metrics, headings),
            f"#outline(title: [{escaped(headings['contents'])}], depth: 2, indent: 1.2em)",
            "#pagebreak()",
            *chapters,
        ]
    )


def _preamble(language: str) -> str:
    return "\n".join(
        [
            f"#set text(font: \"Noto Sans\", size: 11pt, lang: {string_literal(language)})",
            "#show raw: set text(font: \"Noto Sans Mono\")",
            "#set page(margin: 2.2cm, numbering: \"1\")",
            "#set par(justify: true, leading: 0.65em, spacing: 1.2em)",
            "#show heading.where(level: 1): set text(size: 18pt, weight: \"bold\")",
            "#show heading.where(level: 2): set text(size: 14pt, weight: \"bold\")",
            "#show heading: set block(above: 1.5em, below: 0.9em)",
            "#show figure.where(kind: table): set block(breakable: true)",
            "#show table: set par(justify: false)",
        ]
    )


def _package_imports(notes: Notes) -> list[str]:
    block_kinds = {
        block.kind for section in notes.all_sections() for block in section.blocks
    }
    imports = []
    if BlockKind.DIAGRAM in block_kinds:
        imports.append(FLETCHER_IMPORT)
    if BlockKind.CHART in block_kinds:
        imports.append(LILAQ_IMPORT)
    return imports


def _title_page(
    title: str,
    video_file_name: str,
    generation_date: str,
    metrics: LectureMetrics,
    headings: Mapping[str, str],
) -> str:
    return "\n".join(
        [
            "#align(center + horizon)[",
            f"  #text(size: 24pt, weight: \"bold\")[{escaped(title)}]",
            "",
            f"  {escaped(video_file_name)}",
            "",
            f"  {escaped(generation_date)}",
            "",
            _evidence_summary(metrics, headings),
            "]",
            "#pagebreak()",
        ]
    )


def _evidence_summary(metrics: LectureMetrics, headings: Mapping[str, str]) -> str:
    cells = [
        f"      [{escaped(label)}:], [{escaped(value)}],"
        for label, value in _evidence_rows(metrics, headings)
    ]
    return "\n".join(
        [
            "  #text(size: 9pt)[",
            "    #grid(columns: 2, column-gutter: 1em, row-gutter: 0.55em, "
            "align: (right, left),",
            *cells,
            "    )",
            "  ]",
        ]
    )


def _evidence_rows(
    metrics: LectureMetrics, headings: Mapping[str, str]
) -> list[tuple[str, str]]:
    rows = [
        (
            headings["metrics_source_duration"],
            duration_label(metrics.source_duration_seconds),
        ),
        (
            headings["metrics_sections"],
            f"{metrics.section_count} + {metrics.subsection_count}",
        ),
        (headings["metrics_figures"], str(metrics.figure_count)),
        (headings["metrics_tables"], str(metrics.table_count)),
        (headings["metrics_diagrams"], str(metrics.diagram_count)),
    ]
    if metrics.chart_count > 0:
        rows.append((headings["metrics_charts"], str(metrics.chart_count)))
    rows.append((headings["metrics_claims_checked"], _claims_checked_value(metrics)))
    if metrics.model_added_verified > 0:
        rows.append((headings["metrics_model_added"], str(metrics.model_added_verified)))
    rows.append((headings["metrics_questions"], str(metrics.question_count)))
    rows.append(
        (headings["metrics_coverage"], coverage_percent_label(metrics.coverage_ratio))
    )
    return rows


def _claims_checked_value(metrics: LectureMetrics) -> str:
    if metrics.claims_disputed + metrics.claims_mixed == 0:
        return str(metrics.claims_checked)
    return (
        f"{metrics.claims_checked} ({Verdict.DISPUTED.value}: {metrics.claims_disputed}, "
        f"{Verdict.MIXED.value}: {metrics.claims_mixed})"
    )


def _section_chapter(section: NoteSection, headings: Mapping[str, str]) -> str:
    lines = _titled_section_lines("=", section, headings)
    for subsection in section.subsections:
        lines.extend(_titled_section_lines("==", subsection, headings))
    return "\n".join(lines)


def _titled_section_lines(
    heading_marker: str, section: NoteSection, headings: Mapping[str, str]
) -> list[str]:
    lines = [
        f"{heading_marker} {escaped(section.title)}",
        f"#text(size: 9pt, fill: gray)[{_span_labels(section.source_spans)}]",
        "",
    ]
    for block in section.blocks:
        lines.append(_block_markup(block, headings))
        lines.append("")
    return lines


def _block_markup(block: NoteBlock, headings: Mapping[str, str]) -> str:
    if block.kind is BlockKind.FIGURE:
        return _figure_markup(block, headings)
    if block.kind is BlockKind.FACTCHECK_NOTE:
        return _factcheck_markup(block, headings)
    if block.kind is BlockKind.DEFINITION:
        return _definition_markup(block)
    if block.kind is BlockKind.FACT:
        return _fact_markup(block, headings)
    if block.kind is BlockKind.TABLE and block.table is not None:
        return table_markup(block.table, block.caption or "")
    if block.kind is BlockKind.DIAGRAM and block.diagram is not None:
        return diagram_markup(block.diagram, block.caption or "")
    if block.kind is BlockKind.CHART and block.chart is not None:
        return chart_markup(block.chart, block.caption or "")
    return _emphasized(block.text or "")


def _figure_markup(block: NoteBlock, headings: Mapping[str, str]) -> str:
    caption = escaped(block.caption or "")
    image_path = string_literal(block.image_path or "")
    return "\n".join(
        [
            "#figure(",
            "  layout(size => {",
            f"    let full_width = image({image_path}, width: size.width)",
            f"    if measure(full_width).height > {MAX_FIGURE_HEIGHT} "
            f"{{ image({image_path}, height: {MAX_FIGURE_HEIGHT}) }} else {{ full_width }}",
            "  }),",
            f"  caption: [{caption}],",
            ")",
            f"#align(center)[#text(size: 9pt, style: \"italic\")"
            f"[{_figure_attribution(block, headings)}]]",
        ]
    )


def _figure_attribution(block: NoteBlock, headings: Mapping[str, str]) -> str:
    attribution = f"{escaped(headings['source_label'])}: {escaped(block.source_ref or '')}"
    if block.provenance is FigureProvenance.GENERATED:
        return f"{attribution} · {escaped(headings['generated_label'])}"
    return attribution


def _factcheck_markup(block: NoteBlock, headings: Mapping[str, str]) -> str:
    return _callout(
        FACTCHECK_FILL,
        _FACTCHECK_STRIPE,
        [f"  *{escaped(headings['factcheck_label'])}:* {escaped(block.text or '')}"],
    )


def _definition_markup(block: NoteBlock) -> str:
    return _callout(
        DEFINITION_FILL,
        _DEFINITION_STRIPE,
        [
            f"  #text(weight: \"bold\", size: 12pt)[{escaped(block.term or '')}]",
            "",
            f"  {_emphasized(block.text or '')}",
        ],
    )


def _fact_markup(block: NoteBlock, headings: Mapping[str, str]) -> str:
    return _callout(
        FACT_FILL,
        _FACT_STRIPE,
        [
            f"  #text(weight: \"bold\")[{escaped(headings['fact_label'])}]",
            "",
            f"  {_emphasized(block.text or '')}",
        ],
    )


def _callout(fill: str, stripe: str, body_lines: list[str]) -> str:
    opening = (
        f"#block(breakable: false, width: 100%, fill: rgb(\"{fill}\"), "
        f"stroke: (left: 3pt + rgb(\"{stripe}\")), inset: 10pt, radius: 3pt)["
    )
    return "\n".join([opening, *body_lines, "]"])





def _span_labels(source_spans: tuple[TimeRange, ...]) -> str:
    return ", ".join(f"{span.start_label()} – {span.end_label()}" for span in source_spans)


def _emphasized(text: str) -> str:
    fragments = text.split(_EMPHASIS_MARKER)
    if len(fragments) % 2 == 0:
        return escaped(text)
    return "".join(
        f"#text(weight: \"bold\", fill: rgb(\"{_EMPHASIS_TINT}\"))[{escaped(fragment)}]"
        if index % 2 == 1
        else escaped(fragment)
        for index, fragment in enumerate(fragments)
    )

