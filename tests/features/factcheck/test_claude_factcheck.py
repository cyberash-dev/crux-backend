# @covers analysis:EXT-010
import json
from types import SimpleNamespace

import pytest

from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    ClaudeClaimExtraction,
    ClaudeRefusalError,
    FactcheckResponseError,
    parse_extraction_payload,
)
from konspekt.features.factcheck.domain.claims import ExtractedClaim
from konspekt.shared.timecode import TimeRange


class FakeMessages:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = responses
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self._responses[len(self.calls) - 1]


class FakeAnthropicClient:
    def __init__(self, *responses: SimpleNamespace) -> None:
        self.messages = FakeMessages(list(responses))


class RecordingBudget:
    def __init__(self) -> None:
        self.charges: list[float] = []

    def charge(self, cost_usd: float) -> None:
        self.charges.append(cost_usd)


def a_response(
    text: str,
    input_tokens: int = 1000,
    output_tokens: int = 200,
    stop_reason: str = "end_turn",
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        stop_reason=stop_reason,
    )


def an_extraction_payload_text() -> str:
    return json.dumps(
        {
            "claims": [
                {
                    "claim_text": "Скорость света — 300 000 км/с",
                    "span_start_seconds": 12.5,
                    "span_end_seconds": 40.0,
                }
            ]
        }
    )


def test_parse_extraction_payload_maps_claims_with_spans() -> None:
    claims = parse_extraction_payload(an_extraction_payload_text())

    assert claims == [
        ExtractedClaim(
            claim_text="Скорость света — 300 000 км/с",
            span=TimeRange(12.5, 40.0),
        )
    ]


def test_parse_extraction_payload_rejects_malformed_json() -> None:
    with pytest.raises(FactcheckResponseError, match="JSON"):
        parse_extraction_payload("{not json")


def test_parse_extraction_payload_rejects_missing_claims_key() -> None:
    with pytest.raises(FactcheckResponseError, match="claims"):
        parse_extraction_payload("{}")


def test_extraction_charges_budget_from_reported_usage() -> None:
    client = FakeAnthropicClient(
        a_response(an_extraction_payload_text(), input_tokens=1000, output_tokens=200)
    )
    budget = RecordingBudget()
    extraction = ClaudeClaimExtraction(budget=budget, client=client)

    extraction.extract_claims("[00:00:12] core text", "ru")

    assert budget.charges == [pytest.approx(1000 * 5 / 1e6 + 200 * 25 / 1e6)]


def test_extraction_request_omits_thinking_and_temperature() -> None:
    client = FakeAnthropicClient(a_response(an_extraction_payload_text()))
    extraction = ClaudeClaimExtraction(budget=RecordingBudget(), client=client)

    extraction.extract_claims("core text", "en")

    request = client.messages.calls[0]
    assert "thinking" not in request
    assert "temperature" not in request


def test_extraction_refusal_raises_typed_error() -> None:
    client = FakeAnthropicClient(a_response("", stop_reason="refusal"))
    extraction = ClaudeClaimExtraction(budget=RecordingBudget(), client=client)

    with pytest.raises(ClaudeRefusalError):
        extraction.extract_claims("core text", "en")


def test_refusal_still_charges_the_budget() -> None:
    client = FakeAnthropicClient(
        a_response("", input_tokens=500, output_tokens=10, stop_reason="refusal")
    )
    budget = RecordingBudget()
    extraction = ClaudeClaimExtraction(budget=budget, client=client)

    with pytest.raises(ClaudeRefusalError):
        extraction.extract_claims("core text", "en")

    assert budget.charges == [pytest.approx(500 * 5 / 1e6 + 10 * 25 / 1e6)]


def test_extraction_schema_mismatch_is_retried_once_and_succeeds() -> None:
    client = FakeAnthropicClient(
        a_response("{not json", input_tokens=1000, output_tokens=200),
        a_response(an_extraction_payload_text(), input_tokens=1100, output_tokens=300),
    )
    budget = RecordingBudget()
    extraction = ClaudeClaimExtraction(budget=budget, client=client)

    claims = extraction.extract_claims("core text", "ru")

    assert len(claims) == 1
    assert claims[0].claim_text == "Скорость света — 300 000 км/с"
    assert len(client.messages.calls) == 2
    assert budget.charges == [
        pytest.approx(1000 * 5 / 1e6 + 200 * 25 / 1e6),
        pytest.approx(1100 * 5 / 1e6 + 300 * 25 / 1e6),
    ]


def test_extraction_schema_mismatch_twice_fails_after_two_requests() -> None:
    client = FakeAnthropicClient(
        a_response("{not json"),
        a_response('{"unexpected": "shape"}'),
    )
    extraction = ClaudeClaimExtraction(budget=RecordingBudget(), client=client)

    with pytest.raises(FactcheckResponseError, match="claims"):
        extraction.extract_claims("core text", "ru")

    assert len(client.messages.calls) == 2


def test_extraction_refusal_is_not_retried() -> None:
    client = FakeAnthropicClient(a_response("", stop_reason="refusal"))
    extraction = ClaudeClaimExtraction(budget=RecordingBudget(), client=client)

    with pytest.raises(ClaudeRefusalError):
        extraction.extract_claims("core text", "en")

    assert len(client.messages.calls) == 1


def test_model_from_constructor_is_sent_in_request() -> None:
    client = FakeAnthropicClient(a_response(an_extraction_payload_text()))
    extraction = ClaudeClaimExtraction(
        budget=RecordingBudget(), model="claude-opus-4-8", client=client
    )

    extraction.extract_claims("core text", "en")

    assert client.messages.calls[0]["model"] == "claude-opus-4-8"
