# @covers analysis:EXT-011
import json
import os
import stat
from pathlib import Path

import pytest

from konspekt.shared.claude_cli import (
    ClaudeCliBinaryMissingError,
    ClaudeCliError,
    ClaudeCliResult,
    ClaudeCliRunner,
    parse_cli_output,
)


def cli_output(result: str = "answer", is_error: bool = False, cost: float = 0.42) -> str:
    return json.dumps({"result": result, "is_error": is_error, "total_cost_usd": cost})


def test_parse_returns_text_and_cost() -> None:
    parsed = parse_cli_output(cli_output(result="hello", cost=1.25))

    assert parsed == ClaudeCliResult(text="hello", cost_usd=1.25)


def test_parse_rejects_error_flag_with_result_text() -> None:
    with pytest.raises(ClaudeCliError, match="model run failed"):
        parse_cli_output(cli_output(result="boom", is_error=True))


def test_parse_rejects_malformed_json() -> None:
    with pytest.raises(ClaudeCliError, match="not valid JSON"):
        parse_cli_output("{broken")


def test_parse_rejects_missing_result_field() -> None:
    with pytest.raises(ClaudeCliError, match="result"):
        parse_cli_output(json.dumps({"is_error": False, "total_cost_usd": 0.1}))


def a_stub_binary(tmp_path: Path, stdout_json: str) -> Path:
    stub = tmp_path / "claude-stub"
    capture = tmp_path / "invocation.txt"
    stub.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" > "{capture}"\n'
        f'cat >> "{capture}"\n'
        f"cat <<'JSONEOF'\n{stdout_json}\nJSONEOF\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub


def test_runner_passes_prompt_via_stdin_and_model_in_argv(tmp_path: Path) -> None:
    stub = a_stub_binary(tmp_path, cli_output(result="ok", cost=0.05))
    runner = ClaudeCliRunner(binary_name=str(stub))

    result = runner.run("the prompt", model="claude-opus-5", allowed_tools=("WebSearch",))

    invocation = (tmp_path / "invocation.txt").read_text()
    assert result == ClaudeCliResult(text="ok", cost_usd=0.05)
    assert "--model claude-opus-5" in invocation
    assert "--allowedTools WebSearch" in invocation
    assert "the prompt" in invocation


def test_runner_maps_nonzero_exit_to_typed_error(tmp_path: Path) -> None:
    stub = tmp_path / "claude-stub"
    stub.write_text("#!/bin/sh\necho doom >&2\nexit 3\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    with pytest.raises(ClaudeCliError, match="doom"):
        ClaudeCliRunner(binary_name=str(stub)).run("p", model="claude-opus-5")


def test_missing_binary_raises_typed_error() -> None:
    runner = ClaudeCliRunner(binary_name="/nonexistent/claude-binary")

    with pytest.raises(ClaudeCliBinaryMissingError, match="claude"):
        runner.run("p", model="claude-opus-5")


def an_argv_recording_stub(tmp_path: Path, stdout_json: str) -> Path:
    stub = tmp_path / "claude-stub"
    stub.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$@" > "{tmp_path / "argv.txt"}"\n'
        f"cat <<'JSONEOF'\n{stdout_json}\nJSONEOF\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub


def test_runner_passes_tools_system_prompt_file_and_json_schema(tmp_path: Path) -> None:
    """# @covers service:EXT-003"""
    stub = an_argv_recording_stub(tmp_path, cli_output())
    schema = {"type": "object", "required": ["reply"]}

    ClaudeCliRunner(binary_name=str(stub)).run(
        "p", model="sonnet", tools=(), system_prompt_file=tmp_path / "system.md", json_schema=schema
    )

    argv = (tmp_path / "argv.txt").read_text().split("\n")[:-1]
    assert argv[argv.index("--model") + 2 :] == [
        "--tools",
        "",
        "--system-prompt-file",
        str(tmp_path / "system.md"),
        "--json-schema",
        json.dumps(schema),
    ]


def test_runner_without_structured_options_keeps_the_default_invocation(tmp_path: Path) -> None:
    """# @covers service:EXT-003"""
    stub = an_argv_recording_stub(tmp_path, cli_output())

    ClaudeCliRunner(binary_name=str(stub)).run("p", model="claude-opus-5")

    assert (tmp_path / "argv.txt").read_text().split("\n")[:-1] == [
        "-p",
        "--output-format",
        "json",
        "--model",
        "claude-opus-5",
    ]


def test_parse_reads_the_structured_output_object() -> None:
    """# @covers service:EXT-003"""
    stdout = json.dumps(
        {"result": "", "is_error": False, "total_cost_usd": 0.03, "structured_output": {"reply": "hi"}}
    )

    parsed = parse_cli_output(stdout)

    assert parsed == ClaudeCliResult(text="", cost_usd=0.03, structured_output={"reply": "hi"})
