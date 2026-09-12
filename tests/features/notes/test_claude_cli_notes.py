# @covers analysis:EXT-011
# @covers analysis:REQ-025
# @covers analysis:DLT-025
import json
from pathlib import Path

import pytest

from konspekt.features.factcheck.domain.claims import CheckedClaim, Verdict
from konspekt.features.notes.adapters.outbound.claude_cli_notes import (
    ClaudeCliNotesComposition,
)
from konspekt.features.notes.application.artifact import NotesArtifactError
from konspekt.features.notes.domain.notes import BlockKind
from konspekt.features.notes.ports.outbound.notes_llm import IndexedClaim, SectionComposition
from konspekt.features.segmentation.domain.segments import SectionPlanEntry
from konspekt.features.visual.domain.frame import Frame
from konspekt.shared.claude_cli import ClaudeCliError, ClaudeCliResult
from konspekt.shared.timecode import TimeRange
from tests.features.claude_fakes import FakeCliRunner, RecordingBudget

FRAMES_ROOT = Path("/work/run-1")


def an_outline() -> tuple[SectionPlanEntry, ...]:
    return (
        SectionPlanEntry("s1", "Первое начало", TimeRange(0.0, 120.0)),
        SectionPlanEntry("s2", "Второе начало", TimeRange(120.0, 180.0)),
    )


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


def a_relative_frame() -> Frame:
    return Frame(
        timestamp_seconds=30.0,
        image_path=Path("frames/frame_30.png"),
        dhash="0" * 16,
        ocr_text="P-V диаграмма",
    )


def a_blocks_response_text() -> str:
    return json.dumps(
        {
            "blocks": [
                {
                    "kind": "prose",
                    "text": "Энергия сохраняется.",
                    "term": None,
                    "image_path": None,
                    "caption": None,
                    "source_ref": None,
                    "claim_ref": None,
                }
            ]
        }
    )


def a_composition(runner: FakeCliRunner, budget: RecordingBudget) -> ClaudeCliNotesComposition:
    return ClaudeCliNotesComposition(budget=budget, frames_root=FRAMES_ROOT, runner=runner)


def compose_first_section(composition: ClaudeCliNotesComposition) -> SectionComposition:
    outline = an_outline()
    return composition.compose_section(
        outline=outline,
        target=outline[0],
        parent=None,
        core_text="[00:00:00] Энергия сохраняется.",
        claims=[an_indexed_claim()],
        frames=[a_relative_frame()],
        language="ru",
        lecture_title="Термодинамика",
        intro_only=False,
    )


def test_compose_section_returns_blocks_and_charges_reported_cost() -> None:
    budget = RecordingBudget()
    runner = FakeCliRunner(ClaudeCliResult(text=a_blocks_response_text(), cost_usd=0.42))

    blocks = compose_first_section(a_composition(runner, budget)).blocks

    assert blocks[0].kind is BlockKind.PROSE
    assert budget.charged_usd == [pytest.approx(0.42)]


def test_compose_section_forwards_model_and_grants_read_tool() -> None:
    runner = FakeCliRunner(ClaudeCliResult(text=a_blocks_response_text(), cost_usd=0.1))

    compose_first_section(a_composition(runner, RecordingBudget()))

    assert runner.calls[0]["model"] == "claude-opus-5"
    assert runner.calls[0]["allowed_tools"] == ("Read",)


def test_prompt_lists_frames_by_absolute_path_and_carries_style_rules() -> None:
    runner = FakeCliRunner(ClaudeCliResult(text=a_blocks_response_text(), cost_usd=0.1))

    compose_first_section(a_composition(runner, RecordingBudget()))

    prompt = runner.calls[0]["prompt"]
    assert str(FRAMES_ROOT / "frames/frame_30.png") in prompt
    assert "video 00:00:30" in prompt
    assert "claim 4" in prompt
    assert "standalone study text" in prompt
    assert "never glue" in prompt
    assert "Read tool" in prompt
    assert "illustration_request" in prompt


def test_compose_section_retries_once_after_schema_mismatch() -> None:
    budget = RecordingBudget()
    runner = FakeCliRunner(
        ClaudeCliResult(text="{}", cost_usd=0.1),
        ClaudeCliResult(text=a_blocks_response_text(), cost_usd=0.2),
    )

    blocks = compose_first_section(a_composition(runner, budget)).blocks

    assert len(blocks) == 1
    assert len(runner.calls) == 2
    assert budget.charged_usd == [pytest.approx(0.1), pytest.approx(0.2)]


def test_compose_section_fails_after_second_schema_mismatch() -> None:
    budget = RecordingBudget()
    runner = FakeCliRunner(
        ClaudeCliResult(text="{}", cost_usd=0.1),
        ClaudeCliResult(text="{}", cost_usd=0.1),
    )

    with pytest.raises(NotesArtifactError):
        compose_first_section(a_composition(runner, budget))

    assert len(runner.calls) == 2
    assert len(budget.charged_usd) == 2


def test_compose_section_propagates_cli_error_without_retry() -> None:
    budget = RecordingBudget()
    runner = FakeCliRunner(ClaudeCliError("claude model run failed: boom"))

    with pytest.raises(ClaudeCliError, match="boom"):
        compose_first_section(a_composition(runner, budget))

    assert len(runner.calls) == 1
    assert budget.charged_usd == []
