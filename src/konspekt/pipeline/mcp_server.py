import functools
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from konspekt.pipeline import artifacts_query
from konspekt.pipeline.artifacts_query import LectureQueryError
from konspekt.pipeline.run_config import DEFAULT_MAX_LLM_USD, lecture_slug

_ToolReturn = TypeVar("_ToolReturn")


class BuildStartError(Exception):
    def __init__(self, video_path: str) -> None:
        super().__init__(f"video file not found: {video_path}")
        self.video_path = video_path


class BuildSpawner(Protocol):
    def __call__(self, command: list[str], log_path: Path) -> int: ...


def _errors_as_tool_errors(
    tool: Callable[..., _ToolReturn],
) -> Callable[..., _ToolReturn]:
    @functools.wraps(tool)
    def guarded(*args: Any, **kwargs: Any) -> _ToolReturn:
        try:
            return tool(*args, **kwargs)
        except (LectureQueryError, BuildStartError) as error:
            raise ToolError(str(error)) from error

    return guarded


@_errors_as_tool_errors
def list_lectures(out_dir: str = "out") -> list[dict[str, Any]]:
    return artifacts_query.list_lectures(Path(out_dir))


@_errors_as_tool_errors
def lecture_status(slug: str, out_dir: str = "out") -> dict[str, Any]:
    return artifacts_query.lecture_status(Path(out_dir), slug)


@_errors_as_tool_errors
def get_outline(slug: str, out_dir: str = "out") -> dict[str, Any]:
    return artifacts_query.load_outline(Path(out_dir), slug)


@_errors_as_tool_errors
def get_section(slug: str, section_id: str, out_dir: str = "out") -> dict[str, Any]:
    return artifacts_query.load_section(Path(out_dir), slug, section_id)


@_errors_as_tool_errors
def get_cut_log(slug: str, out_dir: str = "out") -> list[dict[str, Any]]:
    return artifacts_query.load_cut_log(Path(out_dir), slug)


@_errors_as_tool_errors
def get_claims(
    slug: str, out_dir: str = "out", verdict: str | None = None
) -> list[dict[str, Any]]:
    return artifacts_query.load_claims(Path(out_dir), slug, verdict)


@_errors_as_tool_errors
def get_quiz(slug: str, out_dir: str = "out") -> dict[str, Any]:
    return artifacts_query.load_quiz(Path(out_dir), slug)


def _spawn_detached(command: list[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_file:
        process = subprocess.Popen(
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return process.pid


def start_build(
    video_path: str,
    out_dir: str = "out",
    lang: str = "auto",
    force_from: str | None = None,
    max_llm_usd: float = DEFAULT_MAX_LLM_USD,
    spawner: BuildSpawner = _spawn_detached,
) -> dict[str, Any]:
    video = Path(video_path)
    if not video.is_file():
        raise BuildStartError(video_path)
    slug = lecture_slug(video.name)
    log_path = Path(out_dir) / slug / "build.log"
    command = [
        "uv",
        "run",
        "konspekt",
        "build",
        str(video),
        "--out",
        out_dir,
        "--lang",
        lang,
        "--max-llm-usd",
        str(max_llm_usd),
    ]
    if force_from is not None:
        command.extend(["--force-from", force_from])
    pid = spawner(command, log_path)
    return {"slug": slug, "log_path": str(log_path), "pid": pid}


def create_server(spawner: BuildSpawner = _spawn_detached) -> MCPServer:
    server = MCPServer(
        name="konspekt",
        instructions=(
            "Query konspekt lecture artifacts (outline, sections, cut log, "
            "claims, quiz) and launch pipeline builds."
        ),
    )
    for reader_tool in (
        list_lectures,
        lecture_status,
        get_outline,
        get_section,
        get_cut_log,
        get_claims,
        get_quiz,
    ):
        server.tool()(reader_tool)

    @server.tool(name="start_build")
    @_errors_as_tool_errors
    def start_build_tool(
        video_path: str,
        out_dir: str = "out",
        lang: str = "auto",
        force_from: str | None = None,
        max_llm_usd: float = DEFAULT_MAX_LLM_USD,
    ) -> dict[str, Any]:
        return start_build(video_path, out_dir, lang, force_from, max_llm_usd, spawner)

    return server


def main() -> None:
    create_server().run("stdio")
