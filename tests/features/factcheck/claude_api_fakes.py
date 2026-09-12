from types import SimpleNamespace


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
