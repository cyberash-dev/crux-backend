from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from konspekt.features.compose.application.labels import labels_for
from konspekt.features.compose.application.metrics import LectureMetrics
from konspekt.features.compose.application.metrics_text import (
    coverage_percent_label,
    duration_label,
)
from konspekt.features.factcheck.domain.claims import CheckedClaim, Verdict
from konspekt.features.notes.domain.audit import VerifiedAddition
from konspekt.features.notes.domain.notes import (
    BlockKind,
    ChartData,
    DiagramData,
    DiagramKind,
    FigureProvenance,
    NoteBlock,
    NoteSection,
    Notes,
    TableData,
)
from konspekt.features.segmentation.domain.segments import LabeledSpan
from konspekt.shared.timecode import TimeRange

README_FILE_NAME = "README.md"
CLAIMS_FILE_NAME = "claims.md"
CUT_LOG_FILE_NAME = "cut-log.md"
SECTIONS_DIR_NAME = "sections"
IMAGES_DIR_NAME = "images"
COMBINED_FILE_NAME = "konspekt.md"
MD_DIR_NAME = "md"

_MERMAID_DIRECTION_BY_KIND = {DiagramKind.HIERARCHY: "TD", DiagramKind.FLOW: "LR"}
_LEDGER_FIRST_VERDICTS = (Verdict.DISPUTED, Verdict.MIXED)


@dataclass(frozen=True, slots=True)
class MarkdownBundle:
    files: Mapping[str, str]
    image_paths: tuple[str, ...]
    combined: str


def render_markdown_bundle(
    notes: Notes,
    claims: Sequence[CheckedClaim],
    cut_spans: Sequence[LabeledSpan],
    video_file_name: str,
    generation_date: str,
    metrics: LectureMetrics,
    verified_additions: Sequence[VerifiedAddition],
) -> MarkdownBundle:
    labels = labels_for(notes.language)
    files: dict[str, str] = {}
    for position, section in enumerate(notes.sections, start=1):
        files[_section_file(position, section)] = _section_markdown(
            section, labels, heading_level=1, image_prefix=IMAGES_DIR_NAME
        )
    files[README_FILE_NAME] = _readme(
        notes, labels, video_file_name, generation_date, metrics
    )
    files[CLAIMS_FILE_NAME] = _claims_markdown(
        claims, verified_additions, labels, heading_level=1
    )
    files[CUT_LOG_FILE_NAME] = _cut_log_markdown(cut_spans, labels, heading_level=1)
    combined = _combined_markdown(
        notes,
        claims,
        cut_spans,
        labels,
        video_file_name,
        generation_date,
        metrics,
        verified_additions,
    )
    return MarkdownBundle(files=files, image_paths=_image_paths(notes), combined=combined)


def section_file_name(position: int, section_id: str) -> str:
    return f"{position:02d}-{section_id}.md"


def _section_file(position: int, section: NoteSection) -> str:
    return f"{SECTIONS_DIR_NAME}/{section_file_name(position, section.section_id)}"


def _readme(
    notes: Notes,
    labels: Mapping[str, str],
    video_file_name: str,
    generation_date: str,
    metrics: LectureMetrics,
) -> str:
    outline_lines: list[str] = []
    for position, section in enumerate(notes.sections, start=1):
        section_path = _section_file(position, section)
        outline_lines.append(f"- [{section.title}]({section_path}) `{section.section_id}`")
        outline_lines.extend(
            f"  - [{subsection.title}]({section_path}#{_anchor(subsection.section_id)}) "
            f"`{subsection.section_id}`"
            for subsection in section.subsections
        )
    return "\n".join(
        [
            *_header_lines(notes, labels, video_file_name, generation_date, metrics),
            f"## {labels['contents']}",
            "",
            *outline_lines,
            "",
            f"- [{labels['claims_title']}]({CLAIMS_FILE_NAME})",
            f"- [{labels['cut_log_title']}]({CUT_LOG_FILE_NAME})",
            "",
        ]
    )


def _combined_markdown(
    notes: Notes,
    claims: Sequence[CheckedClaim],
    cut_spans: Sequence[LabeledSpan],
    labels: Mapping[str, str],
    video_file_name: str,
    generation_date: str,
    metrics: LectureMetrics,
    verified_additions: Sequence[VerifiedAddition],
) -> str:
    outline_lines: list[str] = []
    for section in notes.sections:
        outline_lines.append(
            f"- [{section.title}](#{_anchor(section.section_id)}) `{section.section_id}`"
        )
        outline_lines.extend(
            f"  - [{subsection.title}](#{_anchor(subsection.section_id)}) "
            f"`{subsection.section_id}`"
            for subsection in section.subsections
        )
    image_prefix = f"{MD_DIR_NAME}/{IMAGES_DIR_NAME}"
    parts = [
        "\n".join(
            [
                *_header_lines(notes, labels, video_file_name, generation_date, metrics),
                f"## {labels['contents']}",
                "",
                *outline_lines,
                "",
            ]
        ),
        *(
            _section_markdown(section, labels, heading_level=2, image_prefix=image_prefix)
            for section in notes.sections
        ),
        _claims_markdown(claims, verified_additions, labels, heading_level=2),
        _cut_log_markdown(cut_spans, labels, heading_level=2),
    ]
    return "\n".join(parts)


def _header_lines(
    notes: Notes,
    labels: Mapping[str, str],
    video_file_name: str,
    generation_date: str,
    metrics: LectureMetrics,
) -> list[str]:
    return [
        f"# {notes.title}",
        "",
        f"- {labels['language']}: {notes.language}",
        f"- {labels['source_video']}: {video_file_name}",
        f"- {labels['generated_on']}: {generation_date}",
        "",
        *_metrics_lines(metrics, labels),
        "",
        labels["bundle_note"],
        "",
    ]


def _metrics_lines(metrics: LectureMetrics, labels: Mapping[str, str]) -> list[str]:
    return [
        f"- {labels['metrics_source_duration']}: "
        f"{duration_label(metrics.source_duration_seconds)}",
        f"- {labels['metrics_accounted_duration']}: "
        f"{duration_label(metrics.accounted_duration_seconds)}",
        f"- {labels['metrics_included_duration']}: "
        f"{duration_label(metrics.included_duration_seconds)}",
        f"- {labels['metrics_cut_duration']}: "
        f"{duration_label(metrics.cut_duration_seconds)}",
        f"- {labels['metrics_coverage']}: {coverage_percent_label(metrics.coverage_ratio)}",
        f"- {labels['metrics_claims_checked']}: {metrics.claims_checked}",
        f"- {labels['metrics_questions']}: {metrics.question_count}",
    ]


def _section_markdown(
    section: NoteSection, labels: Mapping[str, str], heading_level: int, image_prefix: str
) -> str:
    lines = [
        f"{_hashes(heading_level)} {section.title} {_anchor_tag(section.section_id)}",
        "",
        f"*{_span_labels(section.source_spans)}*",
        "",
    ]
    lines.extend(_block_lines(section.blocks, labels, image_prefix))
    for subsection in section.subsections:
        lines.extend(
            [
                f"{_hashes(heading_level + 1)} {subsection.title} "
                f"{_anchor_tag(subsection.section_id)}",
                "",
                f"*{_span_labels(subsection.source_spans)}*",
                "",
            ]
        )
        lines.extend(_block_lines(subsection.blocks, labels, image_prefix))
    return "\n".join(lines)


def _hashes(level: int) -> str:
    return "#" * level


def _anchor_tag(section_id: str) -> str:
    return f'<a id="{_anchor(section_id)}"></a>'


def _block_lines(
    blocks: Iterable[NoteBlock], labels: Mapping[str, str], image_prefix: str
) -> list[str]:
    lines: list[str] = []
    for block in blocks:
        lines.append(_block_markdown(block, labels, image_prefix))
        lines.append("")
    return lines


def _block_markdown(block: NoteBlock, labels: Mapping[str, str], image_prefix: str) -> str:
    if block.kind is BlockKind.DEFINITION:
        return f"> **{block.term}** — {block.text}"
    if block.kind is BlockKind.FACT:
        return f"> **{labels['fact_label']}.** {block.text}"
    if block.kind is BlockKind.FACTCHECK_NOTE:
        source = f" ({block.source_ref})" if block.source_ref else ""
        return f"> **{labels['factcheck_label']}.** {block.text}{source}"
    if block.kind is BlockKind.FIGURE:
        return _figure_markdown(block, labels, image_prefix)
    if block.kind is BlockKind.TABLE and block.table is not None:
        return _captioned(_table_markdown(block.table), block.caption)
    if block.kind is BlockKind.DIAGRAM and block.diagram is not None:
        return _captioned(_mermaid_markdown(block.diagram), block.caption)
    if block.kind is BlockKind.CHART and block.chart is not None:
        return _captioned(_chart_markdown(block.chart, labels), block.caption)
    return block.text or ""


def _figure_markdown(block: NoteBlock, labels: Mapping[str, str], image_prefix: str) -> str:
    file_name = PurePosixPath(block.image_path or "").name
    source = f"{labels['source_label']}: {block.source_ref}"
    if block.provenance is FigureProvenance.GENERATED:
        source = f"{source} · {labels['generated_label']}"
    return f"![{block.caption or ''}]({image_prefix}/{file_name})\n\n*{source}*"


def _captioned(body: str, caption: str | None) -> str:
    return f"{body}\n\n*{caption}*" if caption else body


def _table_markdown(table: TableData) -> str:
    return _gfm_table(table.columns, table.rows)


def _chart_markdown(chart: ChartData, labels: Mapping[str, str]) -> str:
    header = (chart.x_title or "", *(one_series.name for one_series in chart.series))
    rows = [
        (category, *(_number(one_series.values[index]) for one_series in chart.series))
        for index, category in enumerate(chart.categories)
    ]
    axis = f" ({chart.y_title})" if chart.y_title else ""
    return f"{labels['chart_kind']}: {chart.kind.value}{axis}\n\n{_gfm_table(header, rows)}"


def _mermaid_markdown(diagram: DiagramData) -> str:
    lines = [f"graph {_MERMAID_DIRECTION_BY_KIND[diagram.kind]}"]
    lines.extend(f'    {node.id}["{_mermaid_text(node.label)}"]' for node in diagram.nodes)
    for edge in diagram.edges:
        arrow = f'-->|"{_mermaid_text(edge.label)}"|' if edge.label else "-->"
        lines.append(f"    {edge.source} {arrow} {edge.target}")
    return "```mermaid\n" + "\n".join(lines) + "\n```"


def _mermaid_text(text: str) -> str:
    return text.replace('"', "#quot;")


def _claims_markdown(
    claims: Sequence[CheckedClaim],
    verified_additions: Sequence[VerifiedAddition],
    labels: Mapping[str, str],
    heading_level: int,
) -> str:
    rows = [
        (
            claim.claim_id,
            claim.claim_text,
            _span_label(claim.span),
            claim.verdict.value,
            claim.annotation or "",
            claim.corrected_text or "",
            ", ".join(claim.sources),
        )
        for claim in _ledger_ordered(claims)
    ]
    header = (
        labels["claim_id"],
        labels["claim"],
        labels["time"],
        labels["verdict"],
        labels["annotation"],
        labels["correction"],
        labels["sources"],
    )
    parts = [
        f"{_hashes(heading_level)} {labels['claims_title']}",
        "",
        _gfm_table(header, rows),
    ]
    if verified_additions:
        parts.extend(
            [
                "",
                f"{_hashes(heading_level + 1)} {labels['model_added_title']}",
                "",
                _model_added_table(verified_additions, labels),
            ]
        )
    return "\n".join(parts) + "\n"


def _ledger_ordered(claims: Sequence[CheckedClaim]) -> list[CheckedClaim]:
    return sorted(
        claims,
        key=lambda claim: (
            0 if claim.verdict in _LEDGER_FIRST_VERDICTS else 1,
            claim.span.start_seconds,
        ),
    )


def _model_added_table(
    verified_additions: Sequence[VerifiedAddition], labels: Mapping[str, str]
) -> str:
    rows = [
        (
            addition.text,
            addition.kind.value,
            addition.origin.value,
            addition.verdict.value,
            addition.action.value,
            addition.annotation or "",
            ", ".join(addition.sources),
        )
        for addition in verified_additions
    ]
    header = (
        labels["text"],
        labels["kind"],
        labels["origin"],
        labels["verdict"],
        labels["action"],
        labels["annotation"],
        labels["sources"],
    )
    return _gfm_table(header, rows)


def _cut_log_markdown(
    cut_spans: Sequence[LabeledSpan], labels: Mapping[str, str], heading_level: int
) -> str:
    rows = [
        (_span_label(span.time_range), span.label.value, span.reason or "")
        for span in sorted(cut_spans, key=lambda span: span.time_range.start_seconds)
    ]
    header = (labels["time"], labels["label"], labels["reason"])
    return f"{_hashes(heading_level)} {labels['cut_log_title']}\n\n{_gfm_table(header, rows)}\n"


def _gfm_table(header: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    lines = [_gfm_row(header), _gfm_row(["---"] * len(header))]
    lines.extend(_gfm_row(row) for row in rows)
    return "\n".join(lines)


def _gfm_row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(_cell(cell) for cell in cells) + " |"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _number(value: float) -> str:
    formatted = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if formatted == "-0" else formatted


def _span_labels(source_spans: tuple[TimeRange, ...]) -> str:
    return ", ".join(_span_label(span) for span in source_spans)


def _span_label(span: TimeRange) -> str:
    return f"{span.start_label()} – {span.end_label()}"


def _anchor(section_id: str) -> str:
    return section_id.replace(".", "")


def _image_paths(notes: Notes) -> tuple[str, ...]:
    return tuple(
        block.image_path
        for section in notes.all_sections()
        for block in section.blocks
        if block.kind is BlockKind.FIGURE and block.image_path is not None
    )
