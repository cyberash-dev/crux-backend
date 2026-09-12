# @covers analysis:EXT-010
# @covers analysis:REQ-025
# @covers analysis:CON-022
# @covers analysis:DLT-025
# @covers analysis:REQ-026
# @covers analysis:REQ-027
# @covers analysis:DLT-031
# @covers analysis:REQ-028
import base64
import json
from pathlib import Path

import pytest

from konspekt.features.factcheck.domain.claims import CheckedClaim, Verdict
from konspekt.features.notes.adapters.outbound.claude_notes import (
    SECTION_MAX_TOKENS,
    SECTION_RESPONSE_SCHEMA,
    ClaudeNotesComposition,
    NotesCompositionRefusedError,
    build_section_prompt,
    frame_image_blocks,
    parse_section_response,
)
from konspekt.features.notes.application.artifact import NotesArtifactError
from konspekt.features.notes.domain.illustration import IllustrationRequest
from konspekt.features.notes.domain.notes import BlockKind, BlockOrigin
from konspekt.features.notes.ports.outbound.notes_llm import IndexedClaim, SectionComposition
from konspekt.features.segmentation.domain.segments import SectionPlanEntry
from konspekt.features.visual.domain.frame import Frame
from konspekt.shared.timecode import TimeRange
from tests.features.claude_fakes import FakeClient, RecordingBudget, a_message

PNG_BYTES = b"\x89PNG\r\n\x1a\nfakepixels"


def an_outline() -> tuple[SectionPlanEntry, ...]:
    return (
        SectionPlanEntry(
            "s1",
            "Первое начало",
            TimeRange(0.0, 120.0),
            subsections=(SectionPlanEntry("s1.1", "Энергия", TimeRange(0.0, 60.0)),),
        ),
        SectionPlanEntry("s2", "Второе начало", TimeRange(120.0, 180.0)),
    )


def a_target() -> SectionPlanEntry:
    return an_outline()[0].subsections[0]


def an_indexed_claim() -> IndexedClaim:
    return IndexedClaim(
        global_index=4,
        claim=CheckedClaim(
            claim_text="КПД может превышать предел Карно",
            span=TimeRange(10.0, 20.0),
            verdict=Verdict.DISPUTED,
            sources=("https://example.com/carnot",),
            annotation="Противоречит второму началу.",
        ),
    )


def a_frame(path: Path, timestamp_seconds: float = 30.0) -> Frame:
    return Frame(
        timestamp_seconds=timestamp_seconds,
        image_path=path,
        dhash="0" * 16,
        ocr_text="P-V диаграмма",
    )


def a_section_prompt(intro_only: bool = False) -> str:
    outline = an_outline()
    return build_section_prompt(
        outline=outline,
        target=outline[0].subsections[0],
        parent=outline[0],
        core_text="[00:00:00] Энергия сохраняется.",
        claims=[an_indexed_claim()],
        frames=[a_frame(Path("frames/frame_30.png"))],
        language="ru",
        lecture_title="Термодинамика",
        intro_only=intro_only,
    )


def a_blocks_payload() -> dict[str, object]:
    return {
        "blocks": [
            {
                "kind": "prose",
                "text": "**Энергия** сохраняется.",
                "term": None,
                "image_path": None,
                "caption": None,
                "source_ref": None,
                "claim_ref": None,
            },
            {
                "kind": "factcheck_note",
                "text": "Противоречит второму началу.",
                "term": None,
                "image_path": None,
                "caption": None,
                "source_ref": "https://example.com/carnot",
                "claim_ref": 4,
            },
        ]
    }


def a_composition(client: FakeClient, budget: RecordingBudget) -> ClaudeNotesComposition:
    return ClaudeNotesComposition(budget=budget, client=client)


def compose_target_section(composition: ClaudeNotesComposition) -> SectionComposition:
    outline = an_outline()
    return composition.compose_section(
        outline=outline,
        target=outline[0].subsections[0],
        parent=outline[0],
        core_text="[00:00:00] Энергия сохраняется.",
        claims=[an_indexed_claim()],
        frames=[],
        language="ru",
        lecture_title="Термодинамика",
        intro_only=False,
    )


def test_prompt_carries_outline_with_target_marker() -> None:
    prompt = a_section_prompt()

    assert "s1: Первое начало" in prompt
    assert "s2: Второе начало" in prompt
    assert "s1.1: Энергия" in prompt
    marked_lines = [
        line for line in prompt.splitlines() if "YOU ARE WRITING THIS SECTION" in line
    ]
    assert len(marked_lines) == 1
    assert "s1.1" in marked_lines[0]


def test_prompt_carries_context_claims_and_frames() -> None:
    prompt = a_section_prompt()

    assert "Термодинамика" in prompt
    assert "ru" in prompt
    assert "[00:00:00] Энергия сохраняется." in prompt
    assert "claim 4" in prompt
    assert "EXACTLY the global indices" in prompt
    assert "video 00:00:30" in prompt
    assert "P-V диаграмма" in prompt
    assert "parent section is s1" in prompt


def test_prompt_carries_coherence_rules() -> None:
    prompt = a_section_prompt()

    assert "do not repeat material" in prompt
    assert "only in the section where the outline introduces it first" in prompt


def test_prompt_carries_standalone_style_rules() -> None:
    prompt = a_section_prompt()

    assert "standalone study text" in prompt
    assert "NEVER mention the lecture, the lecturer" in prompt
    assert "no CJK" in prompt
    assert "never glue" in prompt


def test_intro_only_rule_appears_only_when_requested() -> None:
    assert "ONLY a brief introduction" in a_section_prompt(intro_only=True)
    assert "ONLY a brief introduction" not in a_section_prompt(intro_only=False)


def test_intro_prompt_names_subsection_topics_and_forbids_explaining_them() -> None:
    outline = an_outline()

    prompt = build_section_prompt(
        outline=outline,
        target=outline[0],
        parent=None,
        core_text="[00:00:00] Собственный текст родителя.",
        claims=[],
        frames=[],
        language="ru",
        lecture_title="Термодинамика",
        intro_only=True,
    )

    assert "covered by the subsections" in prompt
    assert "Энергия" in prompt
    assert "Do NOT explain the subsection topics" in prompt
    assert "one transitional sentence" in prompt


def test_frame_image_blocks_encode_png_as_base64(tmp_path: Path) -> None:
    frame_path = tmp_path / "frame_30.png"
    frame_path.write_bytes(PNG_BYTES)

    blocks = frame_image_blocks([a_frame(frame_path)])

    image_blocks = [block for block in blocks if block["type"] == "image"]
    assert len(image_blocks) == 1
    source = image_blocks[0]["source"]
    assert source["type"] == "base64"
    assert source["media_type"] == "image/png"
    assert base64.standard_b64decode(source["data"]) == PNG_BYTES


def a_saved_frame(tmp_path: Path, index: int) -> Frame:
    frame_path = tmp_path / f"frame_{index}.png"
    frame_path.write_bytes(PNG_BYTES)
    return a_frame(frame_path, timestamp_seconds=float(index))


def test_frame_image_blocks_cap_at_twenty_images(tmp_path: Path) -> None:
    frames = [a_saved_frame(tmp_path, index) for index in range(25)]

    blocks = frame_image_blocks(frames)

    image_blocks = [block for block in blocks if block["type"] == "image"]
    assert len(image_blocks) == 20


def test_parse_section_response_builds_blocks() -> None:
    blocks = parse_section_response(
        json.dumps(a_blocks_payload()), allowed_claim_indices=frozenset({4})
    ).blocks

    assert blocks[0].kind is BlockKind.PROSE
    assert blocks[1].kind is BlockKind.FACTCHECK_NOTE
    assert blocks[1].claim_ref == 4


def test_parse_section_response_rejects_claim_ref_outside_allowed_indices() -> None:
    with pytest.raises(NotesArtifactError, match="claim_ref"):
        parse_section_response(
            json.dumps(a_blocks_payload()), allowed_claim_indices=frozenset({1})
        )


def test_parse_section_response_rejects_malformed_json() -> None:
    with pytest.raises(NotesArtifactError, match="JSON"):
        parse_section_response("{not json", allowed_claim_indices=frozenset())


def test_parse_section_response_rejects_unpaired_emphasis() -> None:
    payload = a_blocks_payload()
    payload["blocks"][0]["text"] = "**Непарный маркер."

    with pytest.raises(NotesArtifactError, match=r"\*\*"):
        parse_section_response(json.dumps(payload), allowed_claim_indices=frozenset({4}))


def test_response_schema_wraps_typed_blocks() -> None:
    block_schema = SECTION_RESPONSE_SCHEMA["properties"]["blocks"]["items"]

    assert SECTION_RESPONSE_SCHEMA["required"] == ["blocks"]
    assert "definition" in block_schema["properties"]["kind"]["enum"]
    assert "term" in block_schema["required"]


def test_compose_section_charges_budget_from_reported_usage() -> None:
    budget = RecordingBudget()
    client = FakeClient(a_message(json.dumps(a_blocks_payload())))

    blocks = compose_target_section(a_composition(client, budget)).blocks

    assert len(blocks) == 2
    assert budget.charged_usd == [
        pytest.approx(1000 * 5 / 1_000_000 + 2000 * 25 / 1_000_000)
    ]


def test_compose_section_sends_structured_request_without_sampling_overrides() -> None:
    client = FakeClient(a_message(json.dumps(a_blocks_payload())))

    compose_target_section(a_composition(client, RecordingBudget()))

    request = client.stream_requests[0]
    assert request["model"] == "claude-opus-5"
    assert request["max_tokens"] == SECTION_MAX_TOKENS
    assert request["output_config"]["format"]["schema"] == SECTION_RESPONSE_SCHEMA
    assert "thinking" not in request
    assert "temperature" not in request


def test_compose_section_retries_once_after_schema_mismatch() -> None:
    budget = RecordingBudget()
    client = FakeClient(a_message("{}"), a_message(json.dumps(a_blocks_payload())))

    blocks = compose_target_section(a_composition(client, budget)).blocks

    assert len(blocks) == 2
    assert len(client.stream_requests) == 2
    assert len(budget.charged_usd) == 2


def test_compose_section_fails_after_second_schema_mismatch() -> None:
    budget = RecordingBudget()
    client = FakeClient(a_message("{}"), a_message("{}"))

    with pytest.raises(NotesArtifactError):
        compose_target_section(a_composition(client, budget))

    assert len(client.stream_requests) == 2
    assert len(budget.charged_usd) == 2


def test_compose_section_raises_typed_error_on_refusal() -> None:
    budget = RecordingBudget()
    client = FakeClient(
        a_message(json.dumps(a_blocks_payload()), stop_reason="refusal")
    )

    with pytest.raises(NotesCompositionRefusedError):
        compose_target_section(a_composition(client, budget))

    assert len(budget.charged_usd) == 1


def a_raw_block(**overrides: object) -> dict[str, object]:
    raw_block: dict[str, object] = {
        "kind": "prose",
        "text": "Энергия сохраняется.",
        "term": None,
        "image_path": None,
        "caption": None,
        "source_ref": None,
        "claim_ref": None,
        "provenance": None,
        "origin": None,
        "table": None,
        "diagram": None,
        "chart": None,
        "purpose": None,
        "search_query": None,
        "generation_prompt": None,
    }
    raw_block.update(overrides)
    return raw_block


def an_illustration_request_block() -> dict[str, object]:
    return a_raw_block(
        kind="illustration_request",
        text=None,
        purpose="Лучевая и локтевая кости, вид спереди",
        search_query="radius ulna bones anterior view",
        generation_prompt="Educational textbook illustration of the radius and ulna",
    )


def parse_blocks(*raw_blocks: dict[str, object]) -> object:
    return parse_section_response(
        json.dumps({"blocks": list(raw_blocks)}), allowed_claim_indices=frozenset()
    )


def test_parse_section_response_returns_composition_without_request() -> None:
    composition = parse_blocks(a_raw_block())

    assert [block.kind for block in composition.blocks] == [BlockKind.PROSE]
    assert composition.illustration_request is None


def test_parse_section_response_extracts_illustration_request_at_its_position() -> None:
    composition = parse_blocks(
        a_raw_block(), a_raw_block(text="Второй абзац."), an_illustration_request_block(), a_raw_block(text="Третий.")
    )

    assert len(composition.blocks) == 3
    assert composition.illustration_request == IllustrationRequest(
        purpose="Лучевая и локтевая кости, вид спереди",
        search_query="radius ulna bones anterior view",
        generation_prompt="Educational textbook illustration of the radius and ulna",
        insert_index=2,
    )


def test_parse_section_response_keeps_only_first_illustration_request() -> None:
    second_request = an_illustration_request_block()
    second_request["purpose"] = "Вторая просьба"

    composition = parse_blocks(an_illustration_request_block(), a_raw_block(), second_request)

    assert composition.illustration_request is not None
    assert composition.illustration_request.purpose == "Лучевая и локтевая кости, вид спереди"
    assert composition.illustration_request.insert_index == 0
    assert len(composition.blocks) == 1


def test_parse_section_response_rejects_illustration_request_without_query() -> None:
    with pytest.raises(NotesArtifactError, match="search_query"):
        parse_blocks(a_raw_block(kind="illustration_request", purpose="Кости", search_query=None, generation_prompt="p"))


@pytest.mark.parametrize(
    "kind, field_name, raw_value",
    [
        ("table", "table", {"columns": ["Кость", "Тип"], "rows": [["Лучевая", "трубчатая"]]}),
        (
            "diagram",
            "diagram",
            {
                "kind": "hierarchy",
                "nodes": [{"id": "bones", "label": "Кости"}, {"id": "long", "label": "Трубчатые"}],
                "edges": [{"source": "bones", "target": "long", "label": None}],
            },
        ),
        (
            "diagram",
            "diagram",
            {
                "kind": "flow",
                "nodes": [{"id": "a", "label": "Вдох"}, {"id": "b", "label": "Выдох"}],
                "edges": [{"source": "a", "target": "b", "label": "затем"}],
            },
        ),
        (
            "chart",
            "chart",
            {
                "kind": "bar",
                "categories": ["2020", "2021"],
                "series": [{"name": "Рост", "values": [1, 2]}],
                "x_title": "Год",
                "y_title": "см",
            },
        ),
        (
            "chart",
            "chart",
            {
                "kind": "line",
                "categories": ["0", "1"],
                "series": [{"name": "Температура", "values": [36.6, 37.0]}],
                "x_title": None,
                "y_title": None,
            },
        ),
    ],
    ids=["table", "hierarchy", "flow", "bar", "line"],
)
def test_parse_section_response_accepts_valid_structured_blocks(
    kind: str, field_name: str, raw_value: dict[str, object]
) -> None:
    composition = parse_blocks(
        a_raw_block(kind=kind, text=None, caption="Подпись", **{field_name: raw_value})
    )

    block = composition.blocks[0]
    assert block.kind is BlockKind(kind)
    assert getattr(block, field_name) is not None
    assert block.caption == "Подпись"


@pytest.mark.parametrize(
    "kind, field_name, raw_value, message",
    [
        ("table", "table", {"columns": ["a", "b"], "rows": [["1"]]}, "cells as columns"),
        (
            "diagram",
            "diagram",
            {
                "kind": "flow",
                "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                "edges": [{"source": "a", "target": "zzz", "label": None}],
            },
            "undeclared node",
        ),
        (
            "diagram",
            "diagram",
            {"kind": "flow", "nodes": [{"id": "a", "label": "A"}], "edges": []},
            "two nodes",
        ),
        (
            "chart",
            "chart",
            {
                "kind": "bar",
                "categories": ["x", "y"],
                "series": [{"name": "s", "values": [1]}],
                "x_title": None,
                "y_title": None,
            },
            "values as categories",
        ),
    ],
    ids=["ragged-table", "dangling-edge", "single-node", "series-mismatch"],
)
def test_parse_section_response_rejects_invalid_structured_blocks(
    kind: str, field_name: str, raw_value: dict[str, object], message: str
) -> None:
    with pytest.raises(NotesArtifactError, match=message):
        parse_blocks(a_raw_block(kind=kind, text=None, **{field_name: raw_value}))


def test_response_schema_carries_structured_fields_and_illustration_request() -> None:
    block_schema = SECTION_RESPONSE_SCHEMA["properties"]["blocks"]["items"]

    assert {"table", "diagram", "chart", "provenance"} <= set(block_schema["properties"])
    assert "illustration_request" in block_schema["properties"]["kind"]["enum"]
    assert {"purpose", "search_query", "generation_prompt"} <= set(block_schema["required"])
    assert set(block_schema["properties"]["diagram"]["anyOf"][0]["properties"]) == {
        "kind",
        "nodes",
        "edges",
    }


def test_prompt_carries_structured_block_rules() -> None:
    prompt = a_section_prompt()

    assert "diagram" in prompt and "hierarchy" in prompt and "flow" in prompt
    assert "table" in prompt
    assert "chart" in prompt and "bar" in prompt and "line" in prompt
    assert "data only" in prompt
    assert "short ASCII slugs" in prompt


def test_response_schema_carries_origin_enum() -> None:
    block_schema = SECTION_RESPONSE_SCHEMA["properties"]["blocks"]["items"]

    assert "origin" in block_schema["properties"]
    assert "origin" in block_schema["required"]
    origin_values = block_schema["properties"]["origin"]["anyOf"][0]["enum"]
    assert origin_values == ["lecture", "model_added"]


def test_parse_section_response_maps_origin_on_fact_and_definition() -> None:
    composition = parse_blocks(
        a_raw_block(kind="fact", text="Интересный факт.", origin="model_added"),
        a_raw_block(
            kind="definition",
            term="Диафиз",
            text="Средняя часть кости.",
            origin="lecture",
        ),
    )

    assert composition.blocks[0].origin is BlockOrigin.MODEL_ADDED
    assert composition.blocks[1].origin is BlockOrigin.LECTURE


def without_key(raw_block: dict[str, object], key: str) -> dict[str, object]:
    return {name: value for name, value in raw_block.items() if name != key}


# @covers analysis:CON-022
# @covers analysis:REQ-028
@pytest.mark.parametrize(
    "raw_block",
    [
        a_raw_block(kind="fact", text="Интересный факт."),
        a_raw_block(kind="definition", term="Диафиз", text="Средняя часть кости."),
        without_key(a_raw_block(kind="fact", text="Интересный факт."), "origin"),
    ],
    ids=["null-origin-fact", "null-origin-definition", "missing-origin-key"],
)
def test_parse_section_response_rejects_fact_and_definition_blocks_without_origin(
    raw_block: dict[str, object],
) -> None:
    with pytest.raises(NotesArtifactError, match="origin"):
        parse_blocks(raw_block)


# @covers analysis:REQ-028
def test_compose_section_retries_response_with_a_fact_without_origin() -> None:
    origin_less_fact = a_raw_block(kind="fact", text="Факт без происхождения.")
    lecture_fact = a_raw_block(kind="fact", text="Факт лектора.", origin="lecture")
    client = FakeClient(
        a_message(json.dumps({"blocks": [origin_less_fact]})),
        a_message(json.dumps({"blocks": [lecture_fact]})),
    )

    composition = compose_target_section(a_composition(client, RecordingBudget()))

    assert [block.text for block in composition.blocks] == ["Факт лектора."]


def test_prompt_carries_origin_rules() -> None:
    prompt = a_section_prompt()

    assert '"origin"' in prompt
    assert "model_added" in prompt
    assert "clearly entailed" in prompt


def test_prompt_carries_illustration_request_rules() -> None:
    prompt = a_section_prompt()

    assert "illustration_request" in prompt
    assert "Wikimedia Commons" in prompt
    assert "white background" in prompt
    assert "at most one" in prompt
    assert "HTTPS URL" not in prompt


def test_compose_section_returns_composition_with_request() -> None:
    client = FakeClient(
        a_message(json.dumps({"blocks": [a_raw_block(), an_illustration_request_block()]}))
    )

    composition = compose_target_section(a_composition(client, RecordingBudget()))

    assert len(composition.blocks) == 1
    assert composition.illustration_request is not None
    assert composition.illustration_request.insert_index == 1
