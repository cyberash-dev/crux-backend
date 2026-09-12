# @covers analysis:EXT-010
# @covers analysis:DLT-037
import json

import pytest

from konspekt.features.factcheck.adapters.outbound.claude_claim_translation import (
    ClaudeClaimTranslation,
)
from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    ClaudeRefusalError,
    FactcheckResponseError,
)
from tests.features.factcheck.claude_api_fakes import (
    FakeAnthropicClient,
    RecordingBudget,
    a_response,
)

RUSSIAN_CLAIMS = ["Сортировка слиянием работает за O(n log n)", "Число Пи иррационально"]


def a_translation_text(queries: list[str]) -> str:
    return json.dumps({"queries": queries})


def english_queries() -> list[str]:
    return ["merge sort runs in O(n log n)", "pi is irrational"]


def test_translation_request_sends_no_tools() -> None:
    client = FakeAnthropicClient(a_response(a_translation_text(english_queries())))
    translation = ClaudeClaimTranslation(budget=RecordingBudget(), client=client)

    translation.english_queries(RUSSIAN_CLAIMS, "ru")

    assert "tools" not in client.messages.calls[0]


def test_translation_request_uses_the_configured_model() -> None:
    client = FakeAnthropicClient(a_response(a_translation_text(english_queries())))
    translation = ClaudeClaimTranslation(
        budget=RecordingBudget(), model="claude-opus-4-8", client=client
    )

    translation.english_queries(RUSSIAN_CLAIMS, "ru")

    assert client.messages.calls[0]["model"] == "claude-opus-4-8"


def test_translation_prompt_carries_every_claim() -> None:
    client = FakeAnthropicClient(a_response(a_translation_text(english_queries())))
    translation = ClaudeClaimTranslation(budget=RecordingBudget(), client=client)

    translation.english_queries(RUSSIAN_CLAIMS, "ru")

    request_content = client.messages.calls[0]["messages"][0]["content"]
    assert isinstance(request_content, str)
    assert "1. Сортировка слиянием работает за O(n log n)" in request_content
    assert "2. Число Пи иррационально" in request_content


def test_translation_returns_one_english_query_per_claim() -> None:
    client = FakeAnthropicClient(a_response(a_translation_text(english_queries())))
    translation = ClaudeClaimTranslation(budget=RecordingBudget(), client=client)

    queries = translation.english_queries(RUSSIAN_CLAIMS, "ru")

    assert queries == english_queries()


def test_translation_charges_the_budget_from_reported_usage() -> None:
    client = FakeAnthropicClient(
        a_response(a_translation_text(english_queries()), input_tokens=300, output_tokens=40)
    )
    budget = RecordingBudget()
    translation = ClaudeClaimTranslation(budget=budget, client=client)

    translation.english_queries(RUSSIAN_CLAIMS, "ru")

    assert budget.charges == [pytest.approx(300 * 5 / 1e6 + 40 * 25 / 1e6)]


def test_translation_retries_a_wrong_query_count_once() -> None:
    client = FakeAnthropicClient(
        a_response(a_translation_text(["only one"])),
        a_response(a_translation_text(english_queries())),
    )
    translation = ClaudeClaimTranslation(budget=RecordingBudget(), client=client)

    queries = translation.english_queries(RUSSIAN_CLAIMS, "ru")

    assert len(client.messages.calls) == 2
    assert queries == english_queries()


def test_translation_schema_mismatch_twice_fails_after_two_requests() -> None:
    blank_query = a_translation_text(["merge sort", ""])
    client = FakeAnthropicClient(a_response(blank_query), a_response(blank_query))
    translation = ClaudeClaimTranslation(budget=RecordingBudget(), client=client)

    with pytest.raises(FactcheckResponseError, match="queries"):
        translation.english_queries(RUSSIAN_CLAIMS, "ru")

    assert len(client.messages.calls) == 2


def test_translation_refusal_raises_typed_error() -> None:
    client = FakeAnthropicClient(a_response("", stop_reason="refusal"))
    translation = ClaudeClaimTranslation(budget=RecordingBudget(), client=client)

    with pytest.raises(ClaudeRefusalError, match="refused"):
        translation.english_queries(RUSSIAN_CLAIMS, "ru")
