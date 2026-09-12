import json
import logging
from collections.abc import Sequence
from pathlib import Path

from PIL import Image

from konspekt.features.visual.domain.frame import ContentBox
from konspekt.shared.budget import BudgetPort
from konspekt.shared.claude_cli import ClaudeCliError, ClaudeCliRunner

_logger = logging.getLogger(__name__)
_BOX_FIELDS = ("x", "y", "width", "height")


class ClaudeCliLayoutDetection:
    def __init__(
        self,
        budget: BudgetPort,
        model: str = "claude-opus-5",
        runner: ClaudeCliRunner | None = None,
    ) -> None:
        self._budget = budget
        self._model = model
        self._runner = runner if runner is not None else ClaudeCliRunner()

    def detect_content_box(self, probe_paths: Sequence[Path]) -> ContentBox | None:
        prompt = build_layout_prompt(probe_paths)
        try:
            result = self._runner.run(prompt, self._model, allowed_tools=("Read",))
        except ClaudeCliError as error:
            _logger.warning(
                "visual.layout_cli_failed", extra={"error": str(error)}
            )
            return None
        self._budget.charge(result.cost_usd)
        try:
            return parse_layout_response(result.text)
        except ValueError as error:
            _logger.warning(
                "visual.layout_response_malformed", extra={"error": str(error)}
            )
            return None


class NoLayoutDetection:
    def detect_content_box(self, probe_paths: Sequence[Path]) -> ContentBox | None:
        return None


def build_layout_prompt(probe_paths: Sequence[Path]) -> str:
    probe_lines = []
    for probe_path in probe_paths:
        absolute_path = probe_path.resolve()
        with Image.open(absolute_path) as probe_image:
            width, height = probe_image.size
        probe_lines.append(f"- {absolute_path} ({width}x{height} pixels)")
    return (
        "You are given probe frames sampled from one recorded lecture video. "
        "Open every frame below with the Read tool.\n"
        + "\n".join(probe_lines)
        + "\n\nFind the rectangle of the lecture CONTENT area (slides, board, or shared "
        "screen) that is common to all probe frames. Exclude speaker camera tiles, "
        "chat panels, participant lists, toolbars, and letterbox bars. If the whole "
        "frame is content, return the full frame.\n"
        "Respond with exactly one JSON object in ORIGINAL pixel coordinates of the "
        'frames: {"x": int, "y": int, "width": int, "height": int}. '
        "No markdown fences, no commentary, nothing before or after the object."
    )


def parse_layout_response(text: str) -> ContentBox:
    try:
        raw_box = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"layout response is not valid JSON: {error}") from error
    if not isinstance(raw_box, dict):
        raise ValueError("layout response is not a JSON object")
    for field in _BOX_FIELDS:
        if field not in raw_box:
            raise ValueError(f"layout response is missing field {field!r}")
        if not isinstance(raw_box[field], int) or isinstance(raw_box[field], bool):
            raise ValueError(f"layout response field {field!r} is not an integer")
    return ContentBox(
        x=raw_box["x"], y=raw_box["y"], width=raw_box["width"], height=raw_box["height"]
    )
