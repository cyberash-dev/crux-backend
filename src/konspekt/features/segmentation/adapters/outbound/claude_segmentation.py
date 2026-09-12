import json
from collections.abc import Callable, Mapping, Sequence
from types import TracebackType
from typing import Any, Protocol

import anthropic

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

__all__ = [
    "ClaudeSegmentation",
    "SegmentationRefusalError",
    "SegmentationResponseFormatError",
    "label_spans_prompt",
    "merge_span_windows",
    "parse_labeled_spans",
    "parse_plan_outline",
    "plan_outline_prompt",
    "transcript_windows",
    "usage_cost_usd",
]

PLAN_MAX_TOKENS: int = 8000
LABEL_MAX_TOKENS: int = 32000
STREAMING_THRESHOLD_TOKENS: int = 16000
INPUT_USD_PER_TOKEN: float = 5.0 / 1_000_000
OUTPUT_USD_PER_TOKEN: float = 25.0 / 1_000_000

_SUBSECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "section_id": {"type": "string"},
        "title": {"type": "string"},
        "start_seconds": {"type": "number"},
        "end_seconds": {"type": "number"},
        "subsections": {"type": "array", "maxItems": 0},
    },
    "required": ["section_id", "title", "start_seconds", "end_seconds", "subsections"],
    "additionalProperties": False,
}

PLAN_OUTLINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "lecture_title": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "string"},
                    "title": {"type": "string"},
                    "start_seconds": {"type": "number"},
                    "end_seconds": {"type": "number"},
                    "subsections": {"type": "array", "items": _SUBSECTION_SCHEMA},
                },
                "required": [
                    "section_id",
                    "title",
                    "start_seconds",
                    "end_seconds",
                    "subsections",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["lecture_title", "sections"],
    "additionalProperties": False,
}

LABELED_SPANS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "spans": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_seconds": {"type": "number"},
                    "end_seconds": {"type": "number"},
                    "label": {
                        "type": "string",
                        "enum": ["core", "tangent", "anecdote", "admin"],
                    },
                    "section_id": {"type": ["string", "null"]},
                    "reason": {"type": ["string", "null"]},
                },
                "required": [
                    "start_seconds",
                    "end_seconds",
                    "label",
                    "section_id",
                    "reason",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["spans"],
    "additionalProperties": False,
}


class SegmentationRefusalError(Exception):
    def __init__(self) -> None:
        super().__init__("model refused to produce segmentation output")


class _TextBlockLike(Protocol):
    type: str
    text: str


class _UsageLike(Protocol):
    input_tokens: int
    output_tokens: int


class _MessageLike(Protocol):
    content: Sequence[_TextBlockLike]
    stop_reason: str | None
    usage: _UsageLike


class _FinalMessageSource(Protocol):
    def get_final_message(self) -> _MessageLike: ...


class _MessageStreamManagerLike(Protocol):
    def __enter__(self) -> _FinalMessageSource: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class _MessagesApiLike(Protocol):
    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, str]],
        output_config: dict[str, Any],
    ) -> _MessageLike: ...

    def stream(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, str]],
        output_config: dict[str, Any],
    ) -> _MessageStreamManagerLike: ...


class _ClaudeClientLike(Protocol):
    messages: _MessagesApiLike


def usage_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return input_tokens * INPUT_USD_PER_TOKEN + output_tokens * OUTPUT_USD_PER_TOKEN


class ClaudeSegmentation:
    def __init__(
        self,
        budget: BudgetPort,
        model: str = "claude-opus-5",
        client: _ClaudeClientLike | None = None,
    ) -> None:
        self._budget = budget
        self._model = model
        self._client: _ClaudeClientLike = (
            client if client is not None else anthropic.Anthropic()
        )

    def plan_outline(
        self, transcript: Transcript
    ) -> tuple[str, list[SectionPlanEntry]]:
        return self._parsed_response(
            plan_outline_prompt(transcript),
            PLAN_OUTLINE_SCHEMA,
            PLAN_MAX_TOKENS,
            parse_plan_outline,
        )

    def label_spans(
        self, transcript: Transcript, sections_plan: list[SectionPlanEntry]
    ) -> list[LabeledSpan]:
        window_spans = [
            self._parsed_response(
                label_spans_prompt(window, sections_plan),
                LABELED_SPANS_SCHEMA,
                LABEL_MAX_TOKENS,
                parse_labeled_spans,
            )
            for window in transcript_windows(transcript)
        ]
        return merge_span_windows(window_spans)

    def _parsed_response[T](
        self,
        prompt: str,
        schema: Mapping[str, Any],
        max_tokens: int,
        parse: Callable[[Mapping[str, Any]], T],
    ) -> T:
        try:
            return parse(self._response_payload(prompt, schema, max_tokens))
        except SegmentationResponseFormatError:
            return parse(self._response_payload(prompt, schema, max_tokens))

    def _response_payload(
        self, prompt: str, schema: Mapping[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        message = self._final_message(prompt, schema, max_tokens)
        self._budget.charge(
            usage_cost_usd(message.usage.input_tokens, message.usage.output_tokens)
        )
        if message.stop_reason == "refusal":
            raise SegmentationRefusalError
        text = next(
            (block.text for block in message.content if block.type == "text"), None
        )
        if text is None:
            raise SegmentationResponseFormatError("response has no text block")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise SegmentationResponseFormatError(
                f"response is not valid JSON: {error}"
            ) from error
        if not isinstance(payload, dict):
            raise SegmentationResponseFormatError("response root is not a JSON object")
        return payload

    def _final_message(
        self, prompt: str, schema: Mapping[str, Any], max_tokens: int
    ) -> _MessageLike:
        request_messages = [{"role": "user", "content": prompt}]
        output_config: dict[str, Any] = {
            "format": {"type": "json_schema", "schema": dict(schema)}
        }
        if max_tokens > STREAMING_THRESHOLD_TOKENS:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                messages=request_messages,
                output_config=output_config,
            ) as stream:
                return stream.get_final_message()
        return self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=request_messages,
            output_config=output_config,
        )
