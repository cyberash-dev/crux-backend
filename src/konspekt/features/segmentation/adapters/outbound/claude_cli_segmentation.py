import json
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from konspekt.features.segmentation.adapters.outbound.text_protocol import (
    SegmentationResponseFormatError,
    label_spans_prompt,
    merge_span_windows,
    parse_labeled_spans,
    parse_plan_outline,
    plan_outline_prompt,
    transcript_windows,
)
from konspekt.features.segmentation.domain.segments import (
    LabeledSpan,
    SectionPlanEntry,
)
from konspekt.features.transcription.domain.transcript import Transcript
from konspekt.shared.budget import BudgetPort
from konspekt.shared.claude_cli import ClaudeCliResult, ClaudeCliRunner

JSON_ONLY_INSTRUCTION: str = (
    "Respond with exactly one JSON object and nothing else: no markdown\n"
    "fences, no prose before or after it."
)
PLAN_SHAPE_HINT: str = (
    'The object has the shape {"lecture_title": "...", "sections":\n'
    '[{"section_id": "s1", "title": "...", "start_seconds": 0.0,\n'
    '"end_seconds": 0.0, "subsections": [{"section_id": "s1.1",\n'
    '"title": "...", "start_seconds": 0.0, "end_seconds": 0.0,\n'
    '"subsections": []}]}]}.'
)
SPANS_SHAPE_HINT: str = (
    'The object has the shape {"spans": [{"start_seconds": 0.0,\n'
    '"end_seconds": 0.0, "label": "core", "section_id": "s1",\n'
    '"reason": null}]}.'
)


class _CliRunnerLike(Protocol):
    def run(
        self, prompt: str, model: str, allowed_tools: tuple[str, ...] = ()
    ) -> ClaudeCliResult: ...


class ClaudeCliSegmentation:
    def __init__(
        self,
        budget: BudgetPort,
        model: str = "claude-opus-5",
        runner: _CliRunnerLike | None = None,
    ) -> None:
        self._budget = budget
        self._model = model
        self._runner: _CliRunnerLike = (
            runner if runner is not None else ClaudeCliRunner()
        )

    def plan_outline(
        self, transcript: Transcript
    ) -> tuple[str, list[SectionPlanEntry]]:
        prompt = _cli_prompt(plan_outline_prompt(transcript), PLAN_SHAPE_HINT)
        return self._parsed_response(prompt, parse_plan_outline)

    def label_spans(
        self, transcript: Transcript, sections_plan: list[SectionPlanEntry]
    ) -> list[LabeledSpan]:
        window_spans = [
            self._parsed_response(
                _cli_prompt(label_spans_prompt(window, sections_plan), SPANS_SHAPE_HINT),
                parse_labeled_spans,
            )
            for window in transcript_windows(transcript)
        ]
        return merge_span_windows(window_spans)

    def _parsed_response[T](
        self, prompt: str, parse: Callable[[Mapping[str, Any]], T]
    ) -> T:
        try:
            return parse(self._response_payload(prompt))
        except SegmentationResponseFormatError:
            return parse(self._response_payload(prompt))

    def _response_payload(self, prompt: str) -> dict[str, Any]:
        result = self._runner.run(prompt, self._model)
        self._budget.charge(result.cost_usd)
        return _json_object_in_text(result.text)


def _cli_prompt(base_prompt: str, shape_hint: str) -> str:
    return f"{base_prompt}\n\n{JSON_ONLY_INSTRUCTION}\n{shape_hint}"


def _json_object_in_text(text: str) -> dict[str, Any]:
    opening_index = text.find("{")
    closing_index = text.rfind("}")
    if opening_index == -1 or closing_index <= opening_index:
        raise SegmentationResponseFormatError("response carries no JSON object")
    try:
        payload = json.loads(text[opening_index : closing_index + 1])
    except json.JSONDecodeError as error:
        raise SegmentationResponseFormatError(
            f"response is not valid JSON: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise SegmentationResponseFormatError("response root is not a JSON object")
    return payload
