"""Runner for the subscription-authenticated Claude Code binary
(analysis:EXT-011). Lives in shared/ because three analysis slices share
this single outbound transport; it carries no domain knowledge."""

import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class ClaudeCliError(Exception):
    pass


class ClaudeCliBinaryMissingError(ClaudeCliError):
    def __init__(self, binary_name: str) -> None:
        super().__init__(
            f"claude binary not found: {binary_name!r}; install Claude Code and log in"
        )


@dataclass(frozen=True, slots=True)
class ClaudeCliResult:
    text: str
    cost_usd: float
    structured_output: Mapping[str, object] | None = None


class ClaudeCliRunner:
    def __init__(self, binary_name: str = "claude", timeout_seconds: float = 3600.0) -> None:
        self._binary_name = binary_name
        self._timeout_seconds = timeout_seconds

    def run(
        self,
        prompt: str,
        model: str,
        allowed_tools: tuple[str, ...] = (),
        tools: tuple[str, ...] | None = None,
        system_prompt_file: Path | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> ClaudeCliResult:
        command = [self._binary_name, "-p", "--output-format", "json", "--model", model]
        if allowed_tools:
            command += ["--allowedTools", " ".join(allowed_tools)]
        if tools is not None:
            command += ["--tools", ",".join(tools)]
        if system_prompt_file is not None:
            command += ["--system-prompt-file", str(system_prompt_file)]
        if json_schema is not None:
            command += ["--json-schema", json.dumps(json_schema)]
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
        except FileNotFoundError as error:
            raise ClaudeCliBinaryMissingError(self._binary_name) from error
        except subprocess.TimeoutExpired as error:
            raise ClaudeCliError(
                f"claude run exceeded {self._timeout_seconds:.0f}s timeout"
            ) from error
        if completed.returncode != 0:
            raise ClaudeCliError(
                f"claude exited with {completed.returncode}: {completed.stderr.strip()}"
            )
        return parse_cli_output(completed.stdout)


def parse_cli_output(stdout: str) -> ClaudeCliResult:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise ClaudeCliError(f"claude output is not valid JSON: {error}") from error
    if not isinstance(data, dict) or "result" not in data:
        raise ClaudeCliError("claude output carries no result field")
    if data.get("is_error"):
        raise ClaudeCliError(f"claude model run failed: {data['result']}")
    structured_output = data.get("structured_output")
    return ClaudeCliResult(
        text=str(data["result"]),
        cost_usd=float(data.get("total_cost_usd", 0.0)),
        structured_output=structured_output if isinstance(structured_output, dict) else None,
    )
