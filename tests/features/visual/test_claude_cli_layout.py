import json
from pathlib import Path

import pytest
from PIL import Image

from konspekt.features.visual.adapters.outbound.claude_cli_layout import (
    ClaudeCliLayoutDetection,
    NoLayoutDetection,
)
from konspekt.features.visual.domain.frame import ContentBox
from konspekt.shared.claude_cli import ClaudeCliError, ClaudeCliResult
from tests.features.claude_fakes import FakeCliRunner, RecordingBudget


def a_probe_image(path: Path, size: tuple[int, int] = (160, 120)) -> Path:
    Image.new("RGB", size, color="white").save(path)
    return path


def a_box_response_text() -> str:
    return json.dumps({"x": 12, "y": 10, "width": 100, "height": 90})


def test_valid_box_is_parsed_and_budget_charged(tmp_path: Path) -> None:
    """# @covers extraction:EXT-005"""
    probe = a_probe_image(tmp_path / "probe_000.jpg")
    runner = FakeCliRunner(ClaudeCliResult(text=a_box_response_text(), cost_usd=0.07))
    budget = RecordingBudget()

    content_box = ClaudeCliLayoutDetection(budget=budget, runner=runner).detect_content_box(
        [probe]
    )

    assert content_box == ContentBox(x=12, y=10, width=100, height=90)
    assert budget.charged_usd == [0.07]


def test_prompt_names_probe_paths_and_pixel_size_and_allows_read(tmp_path: Path) -> None:
    """# @covers extraction:EXT-005"""
    first_probe = a_probe_image(tmp_path / "probe_000.jpg", size=(320, 240))
    second_probe = a_probe_image(tmp_path / "probe_001.jpg", size=(320, 240))
    runner = FakeCliRunner(ClaudeCliResult(text=a_box_response_text(), cost_usd=0.0))

    ClaudeCliLayoutDetection(budget=RecordingBudget(), runner=runner, model="m").detect_content_box(
        [first_probe, second_probe]
    )

    call = runner.calls[0]
    assert str(first_probe.resolve()) in call["prompt"]
    assert str(second_probe.resolve()) in call["prompt"]
    assert "320x240" in call["prompt"]
    assert call["model"] == "m"
    assert call["allowed_tools"] == ("Read",)


@pytest.mark.parametrize(
    "result_text",
    [
        "not json at all",
        json.dumps({"x": 1, "y": 2, "width": 3}),
        json.dumps({"x": "1", "y": 2, "width": 3, "height": 4}),
        json.dumps({"x": 1.5, "y": 2, "width": 3, "height": 4}),
        json.dumps({"x": -1, "y": 2, "width": 3, "height": 4}),
        json.dumps({"x": 1, "y": 2, "width": 0, "height": 4}),
        json.dumps([1, 2, 3, 4]),
    ],
)
def test_malformed_result_yields_no_box(tmp_path: Path, result_text: str) -> None:
    """# @covers extraction:EXT-005"""
    probe = a_probe_image(tmp_path / "probe_000.jpg")
    runner = FakeCliRunner(ClaudeCliResult(text=result_text, cost_usd=0.05))

    content_box = ClaudeCliLayoutDetection(
        budget=RecordingBudget(), runner=runner
    ).detect_content_box([probe])

    assert content_box is None


def test_malformed_result_still_charges_budget(tmp_path: Path) -> None:
    """# @covers extraction:EXT-005"""
    probe = a_probe_image(tmp_path / "probe_000.jpg")
    runner = FakeCliRunner(ClaudeCliResult(text="garbage", cost_usd=0.05))
    budget = RecordingBudget()

    ClaudeCliLayoutDetection(budget=budget, runner=runner).detect_content_box([probe])

    assert budget.charged_usd == [0.05]


def test_runner_error_yields_no_box_without_charge(tmp_path: Path) -> None:
    """# @covers extraction:EXT-005"""
    probe = a_probe_image(tmp_path / "probe_000.jpg")
    runner = FakeCliRunner(ClaudeCliError("claude exited with 1"))
    budget = RecordingBudget()

    content_box = ClaudeCliLayoutDetection(budget=budget, runner=runner).detect_content_box(
        [probe]
    )

    assert content_box is None
    assert budget.charged_usd == []


def test_no_layout_detection_returns_none(tmp_path: Path) -> None:
    """# @covers extraction:REQ-011"""
    assert NoLayoutDetection().detect_content_box([tmp_path / "probe_000.jpg"]) is None
