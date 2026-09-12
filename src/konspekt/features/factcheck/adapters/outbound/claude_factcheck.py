import json
from collections.abc import Sequence
from typing import Any

import anthropic

from konspekt.features.factcheck.domain.claims import ExtractedClaim
from konspekt.shared.budget import BudgetPort
from konspekt.shared.timecode import TimeRange

_DEFAULT_MODEL = "claude-opus-5"
_INPUT_USD_PER_TOKEN = 5 / 1e6
_OUTPUT_USD_PER_TOKEN = 25 / 1e6
_EXTRACTION_MAX_TOKENS = 8000

_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_text": {"type": "string"},
                    "span_start_seconds": {"type": "number"},
                    "span_end_seconds": {"type": "number"},
                },
                "required": ["claim_text", "span_start_seconds", "span_end_seconds"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}

EXTRACTION_SYSTEM_PROMPT = (
    "You extract verifiable factual claims from a lecture transcript. "
    "A claim is a statement about the world that can be checked against "
    "authoritative sources: numbers, dates, causal assertions, scientific facts. "
    "Skip opinions, illustrative examples, rhetorical questions, and anecdotes. "
    "Copy claim_text verbatim from the transcript, without paraphrasing. "
    "Use the timestamps surrounding each claim to set span_start_seconds and "
    "span_end_seconds."
)


class ClaudeRefusalError(Exception):
    pass


class FactcheckResponseError(Exception):
    pass


class ClaudeClaimExtraction:
    def __init__(
        self,
        budget: BudgetPort,
        model: str = _DEFAULT_MODEL,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self._budget = budget
        self._model = model
        self._client = client or anthropic.Anthropic()

    def extract_claims(
        self, core_text_with_timestamps: str, language: str
    ) -> list[ExtractedClaim]:
        try:
            return self._request_claims(core_text_with_timestamps, language)
        except FactcheckResponseError:
            # per analysis:EXT-010 error_taxonomy: schema-mismatch in parsed
            # output => one re-request, then the stage fails
            return self._request_claims(core_text_with_timestamps, language)

    def _request_claims(
        self, core_text_with_timestamps: str, language: str
    ) -> list[ExtractedClaim]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=_EXTRACTION_MAX_TOKENS,
            output_config={"format": {"type": "json_schema", "schema": _EXTRACTION_SCHEMA}},
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Lecture language: {language}\n"
                        "Transcript with timestamps:\n"
                        f"{core_text_with_timestamps}"
                    ),
                }
            ],
        )
        charge_usage(self._budget, response)
        reject_refusal(response)
        return parse_extraction_payload(joined_text(response))


def parse_extraction_payload(payload_text: str) -> list[ExtractedClaim]:
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as error:
        raise FactcheckResponseError(
            f"extraction response is not valid JSON: {error}"
        ) from error
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        raise FactcheckResponseError("extraction response is missing the claims array")
    return [
        ExtractedClaim(
            claim_text=raw_claim["claim_text"],
            span=TimeRange(
                raw_claim["span_start_seconds"], raw_claim["span_end_seconds"]
            ),
        )
        for raw_claim in payload["claims"]
    ]


def numbered_claim_list(claim_texts: Sequence[str]) -> str:
    return "\n".join(
        f"{claim_number}. {claim_text}"
        for claim_number, claim_text in enumerate(claim_texts, start=1)
    )


def charge_usage(budget: BudgetPort, response: anthropic.types.Message) -> None:
    budget.charge(
        response.usage.input_tokens * _INPUT_USD_PER_TOKEN
        + response.usage.output_tokens * _OUTPUT_USD_PER_TOKEN
    )


def reject_refusal(response: anthropic.types.Message) -> None:
    if response.stop_reason == "refusal":
        raise ClaudeRefusalError("model refused the fact-check request")


def joined_text(response: anthropic.types.Message) -> str:
    return "".join(block.text for block in response.content if block.type == "text")
