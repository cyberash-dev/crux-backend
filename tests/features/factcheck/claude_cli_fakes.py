from konspekt.shared.claude_cli import ClaudeCliResult


class FakeRunner:
    def __init__(self, *results: ClaudeCliResult) -> None:
        self._results = list(results)
        self.calls: list[dict[str, object]] = []

    def run(
        self, prompt: str, model: str, allowed_tools: tuple[str, ...] = ()
    ) -> ClaudeCliResult:
        self.calls.append({"prompt": prompt, "model": model, "allowed_tools": allowed_tools})
        return self._results[len(self.calls) - 1]


class RecordingBudget:
    def __init__(self) -> None:
        self.charges: list[float] = []

    def charge(self, cost_usd: float) -> None:
        self.charges.append(cost_usd)
