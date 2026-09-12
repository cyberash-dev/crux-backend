import base64
import json
import logging
from collections.abc import Mapping, Sequence

from anthropic import Anthropic

from konspekt.features.notes.application.artifact import (
    NotesArtifactError,
    has_unbalanced_emphasis,
    parse_block_payload,
)
from konspekt.features.notes.domain.illustration import IllustrationRequest
from konspekt.features.notes.domain.notes import BlockKind, NoteBlock
from konspekt.features.notes.ports.outbound.notes_llm import (
    IndexedClaim,
    SectionComposition,
)
from konspekt.features.segmentation.domain.segments import SectionPlanEntry
from konspekt.features.visual.domain.frame import Frame
from konspekt.shared.budget import BudgetPort

SECTION_MAX_TOKENS = 16_000
MAX_FRAME_IMAGES = 20

_INPUT_USD_PER_TOKEN = 5 / 1_000_000
_OUTPUT_USD_PER_TOKEN = 25 / 1_000_000

_MEDIA_TYPE_BY_SUFFIX = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

_TARGET_MARKER = "<-- YOU ARE WRITING THIS SECTION"

_logger = logging.getLogger(__name__)

ILLUSTRATION_REQUEST_KIND = "illustration_request"

_NULLABLE_STRING: dict[str, object] = {"type": ["string", "null"]}
_STRING_ARRAY: dict[str, object] = {"type": "array", "items": {"type": "string"}}

_TABLE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "columns": _STRING_ARRAY,
        "rows": {"type": "array", "items": _STRING_ARRAY},
    },
    "required": ["columns", "rows"],
    "additionalProperties": False,
}

_DIAGRAM_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["hierarchy", "flow"]},
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "label": {"type": "string"}},
                "required": ["id", "label"],
                "additionalProperties": False,
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "label": _NULLABLE_STRING,
                },
                "required": ["source", "target", "label"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["kind", "nodes", "edges"],
    "additionalProperties": False,
}

_CHART_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["bar", "line"]},
        "categories": _STRING_ARRAY,
        "series": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "values": {"type": "array", "items": {"type": "number"}},
                },
                "required": ["name", "values"],
                "additionalProperties": False,
            },
        },
        "x_title": _NULLABLE_STRING,
        "y_title": _NULLABLE_STRING,
    },
    "required": ["kind", "categories", "series", "x_title", "y_title"],
    "additionalProperties": False,
}


def _nullable(schema: dict[str, object]) -> dict[str, object]:
    return {"anyOf": [schema, {"type": "null"}]}


_ORIGIN_SCHEMA: dict[str, object] = _nullable(
    {"type": "string", "enum": ["lecture", "model_added"]}
)

_BLOCK_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": [
                "prose",
                "definition",
                "fact",
                "figure",
                "factcheck_note",
                "table",
                "diagram",
                "chart",
                ILLUSTRATION_REQUEST_KIND,
            ],
        },
        "text": _NULLABLE_STRING,
        "term": _NULLABLE_STRING,
        "image_path": _NULLABLE_STRING,
        "caption": _NULLABLE_STRING,
        "source_ref": _NULLABLE_STRING,
        "claim_ref": {"type": ["integer", "null"]},
        "provenance": _NULLABLE_STRING,
        "origin": _ORIGIN_SCHEMA,
        "table": _nullable(_TABLE_SCHEMA),
        "diagram": _nullable(_DIAGRAM_SCHEMA),
        "chart": _nullable(_CHART_SCHEMA),
        "purpose": _NULLABLE_STRING,
        "search_query": _NULLABLE_STRING,
        "generation_prompt": _NULLABLE_STRING,
    },
    "required": [
        "kind",
        "text",
        "term",
        "image_path",
        "caption",
        "source_ref",
        "claim_ref",
        "provenance",
        "origin",
        "table",
        "diagram",
        "chart",
        "purpose",
        "search_query",
        "generation_prompt",
    ],
    "additionalProperties": False,
}

SECTION_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"blocks": {"type": "array", "items": _BLOCK_SCHEMA}},
    "required": ["blocks"],
    "additionalProperties": False,
}


class NotesCompositionRefusedError(Exception):
    pass


def build_section_prompt(
    outline: Sequence[SectionPlanEntry],
    target: SectionPlanEntry,
    parent: SectionPlanEntry | None,
    core_text: str,
    claims: Sequence[IndexedClaim],
    frames: Sequence[Frame],
    language: str,
    lecture_title: str,
    intro_only: bool,
) -> str:
    claim_parts = [
        f"- claim {indexed_claim.global_index}: {indexed_claim.claim.claim_text!r} | "
        f"verdict: {indexed_claim.claim.verdict.value} | "
        f"annotation: {indexed_claim.claim.annotation or '-'} | "
        f"sources: {', '.join(indexed_claim.claim.sources) or '-'}"
        for indexed_claim in claims
    ]
    frame_parts = [
        f"- {_frame_label(frame)} | path: {frame.image_path} | ocr: {frame.ocr_text or '-'}"
        for frame in frames
    ]
    parent_line = (
        f"Its parent section is {parent.section_id}: {parent.title}.\n"
        if parent is not None
        else ""
    )
    subsection_titles = ", ".join(
        subsection.title for subsection in target.subsections
    )
    intro_rule = (
        "- Write ONLY a brief introduction (1-2 paragraphs of prose) for this "
        "section — no definitions, no details: those belong to its subsections. "
        "Introduce the part; the topics below are covered by the subsections: "
        f"{subsection_titles}. Do NOT explain the subsection topics; name them "
        "at most in one transitional sentence.\n"
        if intro_only
        else ""
    )
    return (
        f"You are writing ONE section of the study notes for the lecture "
        f"{lecture_title!r}: section {target.section_id}: {target.title}.\n"
        + parent_line
        + f"Write every text field in the language of the lecture "
        f"(language code: {language}).\n"
        "Rules:\n"
        '- Return the ordered content blocks of this section as {"blocks": [...]}.\n'
        + intro_rule +
        "- Write a standalone study text on the subject. NEVER mention the lecture, "
        "the lecturer, the recording, slides, the platform, or the audience.\n"
        "- No meta-discourse: not 'the lecture opens with', not 'the lecturer "
        "emphasizes' — state the material directly, e.g. 'Анатомия изучает ...'. "
        "(Figure source_ref attribution like 'video HH:MM:SS' is not meta-discourse "
        "and stays as specified.)\n"
        "- Output text only in the lecture language (plus Latin scientific terms "
        "where standard). Never emit characters from other scripts (no CJK etc.).\n"
        "- Mark each key term as **term** at its first appearance; use the emphasis "
        "sparingly, for key terms only. **term** must wrap the term only; keep "
        "normal spaces around the marked term; never glue the emphasized term to "
        "the following word.\n"
        "- Put every definition into its own definition block: term carries the "
        "defined term, text carries a clear formulation.\n"
        "- Put curious or memorable facts into fact blocks.\n"
        '- Every fact and definition block MUST carry "origin": "lecture" when '
        "the statement is directly stated or clearly entailed by the lecture "
        'transcript, "model_added" when you add context, examples or '
        "interesting facts beyond it.\n"
        "- Coherence with the rest of the notes: do not repeat material that "
        "belongs to other sections of the outline; introduce a term with a "
        "definition block only in the section where the outline introduces it "
        "first — elsewhere just use the term.\n"
        "- For every claim listed below with verdict 'disputed', add a "
        "factcheck_note block: text carries the annotation, source_ref carries a "
        "source. claim_ref MUST use EXACTLY the global indices listed below.\n"
        "- figure blocks illustrate the section with one of the provided frames: "
        "image_path is the frame path, source_ref is the frame label "
        "'video HH:MM:SS', provenance is 'video_frame'. Never invent image paths "
        "or URLs.\n"
        "- Structured material becomes typed blocks in addition to the prose: a "
        "classification or hierarchy becomes a diagram block of kind hierarchy; "
        "an ordered process or sequence becomes a diagram block of kind flow; a "
        "comparison of several items along the same properties or a property "
        "matrix becomes a table block (columns + rows, every row has exactly as "
        "many cells as there are columns); a numeric series becomes a chart block "
        "of kind bar or line (every series has exactly as many values as there "
        "are categories). Structured blocks are data only (no markup, no ** "
        "emphasis), carry a caption in the lecture language, may complement the "
        "prose, and are never invented when the material is not structured. "
        "Diagram node ids are short ASCII slugs; node labels are in the lecture "
        "language; edges reference declared node ids only; a diagram has at least "
        "two nodes.\n"
        "- When the section needs an illustration that NO provided frame covers "
        "(e.g. an anatomical structure discussed without a slide), emit ONE block "
        "of kind illustration_request at the position where the figure belongs: "
        "purpose is one sentence in the lecture language describing exactly what "
        "must be depicted (it becomes the caption); search_query is a short "
        "English Wikimedia Commons query (e.g. 'radius ulna bones anterior "
        "view'); generation_prompt is a detailed English prompt for an "
        "educational textbook-style illustration with a white background and "
        "labels in the lecture language. Never request illustrations for "
        "abstract content; at most one illustration_request per section.\n"
        "\n## Global outline\n" + _outline_text(outline, target) +
        "\n\n## Core transcript text of this section\n" + core_text +
        "\n\n## Checked claims (global indices)\n" + ("\n".join(claim_parts) or "(none)") +
        "\n\n## Available frames of this section\n" + ("\n".join(frame_parts) or "(none)")
    )


def frame_image_blocks(frames: Sequence[Frame]) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    for frame in frames[:MAX_FRAME_IMAGES]:
        media_type = _MEDIA_TYPE_BY_SUFFIX.get(frame.image_path.suffix.lower())
        if media_type is None:
            continue
        encoded_image = base64.standard_b64encode(frame.image_path.read_bytes()).decode()
        blocks.append({"type": "text", "text": f"{_frame_label(frame)} ({frame.image_path})"})
        blocks.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": encoded_image},
            }
        )
    return blocks


def parse_section_response(
    raw_text: str, allowed_claim_indices: frozenset[int]
) -> SectionComposition:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise NotesArtifactError(f"section response is not valid JSON: {error}") from error
    try:
        raw_blocks = payload["blocks"]
    except (KeyError, TypeError) as error:
        raise NotesArtifactError("section response carries no blocks field") from error
    blocks: list[NoteBlock] = []
    illustration_request: IllustrationRequest | None = None
    for raw_block in raw_blocks:
        if _is_illustration_request(raw_block):
            if illustration_request is None:
                illustration_request = _parse_illustration_request(raw_block, len(blocks))
            else:
                _logger.warning(
                    "notes.extra_illustration_request_ignored",
                    extra={"purpose": raw_block.get("purpose")},
                )
            continue
        blocks.append(parse_block_payload(raw_block))
    _reject_claim_and_emphasis_violations(blocks, allowed_claim_indices)
    _reject_blocks_without_origin(blocks)
    return SectionComposition(
        blocks=tuple(blocks), illustration_request=illustration_request
    )


def _is_illustration_request(raw_block: object) -> bool:
    return isinstance(raw_block, Mapping) and raw_block.get("kind") == ILLUSTRATION_REQUEST_KIND


def _parse_illustration_request(
    raw_block: Mapping[str, object], insert_index: int
) -> IllustrationRequest:
    try:
        return IllustrationRequest(
            purpose=str(raw_block["purpose"] or ""),
            search_query=str(raw_block["search_query"] or ""),
            generation_prompt=str(raw_block["generation_prompt"] or ""),
            insert_index=insert_index,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise NotesArtifactError(f"invalid illustration request: {error!r}") from error


def _reject_claim_and_emphasis_violations(
    blocks: Sequence[NoteBlock], allowed_claim_indices: frozenset[int]
) -> None:
    for block in blocks:
        if block.claim_ref is not None and block.claim_ref not in allowed_claim_indices:
            raise NotesArtifactError(
                f"claim_ref {block.claim_ref} is not among the allowed global "
                f"indices {sorted(allowed_claim_indices)}"
            )
        if block.text is not None and has_unbalanced_emphasis(block.text):
            raise NotesArtifactError(
                f"block text carries an unpaired ** emphasis marker: {block.text!r}"
            )


def _reject_blocks_without_origin(blocks: Sequence[NoteBlock]) -> None:
    for block in blocks:
        if block.kind in (BlockKind.FACT, BlockKind.DEFINITION) and block.origin is None:
            raise NotesArtifactError(f"{block.kind} block carries no origin")


class ClaudeNotesComposition:
    def __init__(
        self,
        budget: BudgetPort,
        client: Anthropic | None = None,
        model: str = "claude-opus-5",
    ) -> None:
        self._budget = budget
        self._client = client if client is not None else Anthropic()
        self._model = model

    def compose_section(
        self,
        outline: Sequence[SectionPlanEntry],
        target: SectionPlanEntry,
        parent: SectionPlanEntry | None,
        core_text: str,
        claims: Sequence[IndexedClaim],
        frames: Sequence[Frame],
        language: str,
        lecture_title: str,
        intro_only: bool,
    ) -> SectionComposition:
        prompt = build_section_prompt(
            outline, target, parent, core_text, claims, frames, language,
            lecture_title, intro_only,
        )
        content: list[dict[str, object]] = [
            {"type": "text", "text": prompt},
            *frame_image_blocks(frames),
        ]
        allowed_claim_indices = frozenset(
            indexed_claim.global_index for indexed_claim in claims
        )
        try:
            return self._requested_composition(content, allowed_claim_indices)
        except NotesArtifactError:
            return self._requested_composition(content, allowed_claim_indices)

    def _requested_composition(
        self, content: list[dict[str, object]], allowed_claim_indices: frozenset[int]
    ) -> SectionComposition:
        with self._client.messages.stream(
            model=self._model,
            max_tokens=SECTION_MAX_TOKENS,
            messages=[{"role": "user", "content": content}],
            output_config={
                "format": {"type": "json_schema", "schema": SECTION_RESPONSE_SCHEMA}
            },
        ) as stream:
            message = stream.get_final_message()
        self._budget.charge(
            message.usage.input_tokens * _INPUT_USD_PER_TOKEN
            + message.usage.output_tokens * _OUTPUT_USD_PER_TOKEN
        )
        if message.stop_reason == "refusal":
            raise NotesCompositionRefusedError(
                "section composition request was refused by the model"
            )
        raw_text = next(block.text for block in message.content if block.type == "text")
        return parse_section_response(raw_text, allowed_claim_indices)


def _outline_text(outline: Sequence[SectionPlanEntry], target: SectionPlanEntry) -> str:
    lines: list[str] = []
    for entry in outline:
        lines.append(_outline_line(entry, target, indent=""))
        lines.extend(
            _outline_line(subsection, target, indent="  ")
            for subsection in entry.subsections
        )
    return "\n".join(lines)


def _outline_line(entry: SectionPlanEntry, target: SectionPlanEntry, indent: str) -> str:
    marker = f"  {_TARGET_MARKER}" if entry.section_id == target.section_id else ""
    return (
        f"{indent}- {entry.section_id}: {entry.title} "
        f"[{entry.time_range.start_label()} - {entry.time_range.end_label()}]{marker}"
    )


def _frame_label(frame: Frame) -> str:
    whole_seconds = int(frame.timestamp_seconds)
    return (
        f"video {whole_seconds // 3600:02d}:"
        f"{whole_seconds % 3600 // 60:02d}:{whole_seconds % 60:02d}"
    )
