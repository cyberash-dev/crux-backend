from types import SimpleNamespace


class RecordingBudget:
    def __init__(self) -> None:
        self.charged_usd: list[float] = []

    def charge(self, cost_usd: float) -> None:
        self.charged_usd.append(cost_usd)


class FakeStream:
    def __init__(self, message: SimpleNamespace) -> None:
        self._message = message

    def __enter__(self) -> "FakeStream":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def get_final_message(self) -> SimpleNamespace:
        return self._message


class FakeClient:
    def __init__(self, *messages: SimpleNamespace) -> None:
        self.stream_requests: list[dict[str, object]] = []
        self._pending_messages = list(messages)
        outer = self

        class Messages:
            def stream(self, **kwargs: object) -> FakeStream:
                outer.stream_requests.append(kwargs)
                return FakeStream(outer._pending_messages.pop(0))

        self.messages = Messages()


class FakeCliRunner:
    def __init__(self, *outcomes: object) -> None:
        self.calls: list[dict[str, object]] = []
        self._pending_outcomes = list(outcomes)

    def run(
        self, prompt: str, model: str, allowed_tools: tuple[str, ...] = ()
    ) -> object:
        self.calls.append({"prompt": prompt, "model": model, "allowed_tools": allowed_tools})
        outcome = self._pending_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def a_message(raw_text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=1000, output_tokens=2000),
        content=[SimpleNamespace(type="text", text=raw_text)],
    )
