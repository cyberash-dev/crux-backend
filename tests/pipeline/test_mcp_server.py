# @covers pipeline:CON-003
import asyncio
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from konspekt.pipeline import artifacts_query, mcp_server
from konspekt.pipeline.mcp_server import BuildStartError, create_server, start_build
from konspekt.pipeline.run_config import lecture_slug
from tests.pipeline.test_artifacts_query import a_lecture

CONTRACT_TOOL_NAMES = {
    "list_lectures",
    "lecture_status",
    "start_build",
    "get_outline",
    "get_section",
    "get_cut_log",
    "get_claims",
    "get_quiz",
}


class RecordingSpawner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.log_paths: list[Path] = []
        self.wait_called = False

    def __call__(self, command: list[str], log_path: Path) -> int:
        self.commands.append(list(command))
        self.log_paths.append(log_path)
        return 4242

    def wait(self) -> None:
        self.wait_called = True


def test_server_exposes_every_contract_tool() -> None:
    server = create_server()

    tools = asyncio.run(server.list_tools())

    assert {tool.name for tool in tools} == CONTRACT_TOOL_NAMES


def test_list_lectures_delegates_to_reader(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    result = mcp_server.list_lectures(out_dir=str(out_dir))

    assert result == artifacts_query.list_lectures(out_dir)


def test_lecture_status_delegates_to_reader(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    result = mcp_server.lecture_status(slug="lekciya-an-1", out_dir=str(out_dir))

    assert result == artifacts_query.lecture_status(out_dir, "lekciya-an-1")


def test_get_outline_delegates_to_reader(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    result = mcp_server.get_outline(slug="lekciya-an-1", out_dir=str(out_dir))

    assert result == artifacts_query.load_outline(out_dir, "lekciya-an-1")


def test_get_section_delegates_to_reader(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    result = mcp_server.get_section(
        slug="lekciya-an-1", section_id="s1.1", out_dir=str(out_dir)
    )

    assert result == artifacts_query.load_section(out_dir, "lekciya-an-1", "s1.1")


def test_get_cut_log_delegates_to_reader(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    result = mcp_server.get_cut_log(slug="lekciya-an-1", out_dir=str(out_dir))

    assert result == artifacts_query.load_cut_log(out_dir, "lekciya-an-1")


def test_get_claims_delegates_with_verdict_filter(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    result = mcp_server.get_claims(
        slug="lekciya-an-1", out_dir=str(out_dir), verdict="disputed"
    )

    assert result == artifacts_query.load_claims(out_dir, "lekciya-an-1", "disputed")


def test_get_quiz_delegates_to_reader(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    result = mcp_server.get_quiz(slug="lekciya-an-1", out_dir=str(out_dir))

    assert result == artifacts_query.load_quiz(out_dir, "lekciya-an-1")


def test_unknown_slug_surfaces_as_tool_error_with_reader_text(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    with pytest.raises(ToolError, match="lecture 'nope' not found"):
        mcp_server.get_outline(slug="nope", out_dir=str(out_dir))


def test_missing_artifact_surfaces_as_tool_error(tmp_path: Path) -> None:
    slug = "lekciya-an-1"
    out_dir = a_lecture(tmp_path)
    (out_dir / slug / "quiz.json").unlink()

    with pytest.raises(ToolError, match="quiz export is missing"):
        mcp_server.get_quiz(slug=slug, out_dir=str(out_dir))


def test_start_build_spawns_build_command_with_video_lang_and_force_from(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "Лекция об анатомии.mp4"
    video_path.write_bytes(b"fake video")
    spawner = RecordingSpawner()

    start_build(
        video_path=str(video_path),
        out_dir=str(tmp_path / "out"),
        lang="ru",
        force_from="notes",
        max_llm_usd=5.0,
        spawner=spawner,
    )

    command = spawner.commands[0]
    assert command[:4] == ["uv", "run", "konspekt", "build"]
    assert str(video_path) in command
    assert command[command.index("--lang") + 1] == "ru"
    assert command[command.index("--force-from") + 1] == "notes"
    assert command[command.index("--max-llm-usd") + 1] == "5.0"


def test_start_build_omits_force_from_by_default(tmp_path: Path) -> None:
    video_path = tmp_path / "lecture.mp4"
    video_path.write_bytes(b"fake video")
    spawner = RecordingSpawner()

    start_build(video_path=str(video_path), out_dir=str(tmp_path / "out"), spawner=spawner)

    assert "--force-from" not in spawner.commands[0]


def test_start_build_places_log_under_out_slug(tmp_path: Path) -> None:
    video_path = tmp_path / "Лекция об анатомии.mp4"
    video_path.write_bytes(b"fake video")
    expected_slug = lecture_slug(video_path.name)
    spawner = RecordingSpawner()

    result = start_build(
        video_path=str(video_path), out_dir=str(tmp_path / "out"), spawner=spawner
    )

    expected_log_path = tmp_path / "out" / expected_slug / "build.log"
    assert result["slug"] == expected_slug
    assert result["log_path"] == str(expected_log_path)
    assert spawner.log_paths == [expected_log_path]


def test_start_build_returns_spawner_pid_without_waiting(tmp_path: Path) -> None:
    video_path = tmp_path / "lecture.mp4"
    video_path.write_bytes(b"fake video")
    spawner = RecordingSpawner()

    result = start_build(
        video_path=str(video_path), out_dir=str(tmp_path / "out"), spawner=spawner
    )

    assert result["pid"] == 4242
    assert spawner.wait_called is False


def test_start_build_rejects_missing_video_before_spawn(tmp_path: Path) -> None:
    missing_video_path = tmp_path / "absent.mp4"
    spawner = RecordingSpawner()

    with pytest.raises(BuildStartError, match="absent.mp4"):
        start_build(
            video_path=str(missing_video_path),
            out_dir=str(tmp_path / "out"),
            spawner=spawner,
        )

    assert spawner.commands == []
