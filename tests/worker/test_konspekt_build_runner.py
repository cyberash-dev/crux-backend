# @covers service:REQ-002
import signal
from pathlib import Path

from konspekt.worker.adapters.outbound.konspekt_build_runner import KonspektBuildRunner
from tests.worker.stub_processes import (
    a_stub_executable,
    an_outcome_after_exit,
    recording_arguments_to,
)


def a_konspekt(tmp_path: Path, body: str) -> str:
    return a_stub_executable(tmp_path, "konspekt", body)


def test_build_command_passes_video_out_dir_language_and_budget(tmp_path: Path) -> None:
    args_log_path = tmp_path / "args.log"
    runner = KonspektBuildRunner(
        log_dir=tmp_path, binary=a_konspekt(tmp_path, recording_arguments_to(args_log_path))
    )

    an_outcome_after_exit(
        runner.start(tmp_path / "HtSuA80QTyo.mkv", tmp_path / "out", "ru", 60.0)
    )

    assert args_log_path.read_text().splitlines() == [
        "build",
        str(tmp_path / "HtSuA80QTyo.mkv"),
        "-o",
        str(tmp_path / "out"),
        "--lang",
        "ru",
        "--max-llm-usd",
        "60.0",
    ]


def test_build_outcome_carries_the_exit_code(tmp_path: Path) -> None:
    runner = KonspektBuildRunner(log_dir=tmp_path, binary=a_konspekt(tmp_path, "exit 2\n"))

    outcome = an_outcome_after_exit(
        runner.start(tmp_path / "HtSuA80QTyo.mkv", tmp_path / "out", "auto", 60.0)
    )

    assert outcome.exit_code == 2


def test_total_spend_line_becomes_the_llm_spend(tmp_path: Path) -> None:
    runner = KonspektBuildRunner(
        log_dir=tmp_path,
        binary=a_konspekt(
            tmp_path, 'echo "done: out/htsua80qtyo/konspekt.pdf"\necho "total spend: 12.34 USD"\n'
        ),
    )

    outcome = an_outcome_after_exit(
        runner.start(tmp_path / "HtSuA80QTyo.mkv", tmp_path / "out", "auto", 60.0)
    )

    assert outcome.llm_spend_usd == 12.34


def test_missing_total_spend_line_leaves_the_llm_spend_unknown(tmp_path: Path) -> None:
    runner = KonspektBuildRunner(
        log_dir=tmp_path,
        binary=a_konspekt(tmp_path, 'echo "error: missing required env vars" >&2\nexit 2\n'),
    )

    outcome = an_outcome_after_exit(
        runner.start(tmp_path / "HtSuA80QTyo.mkv", tmp_path / "out", "auto", 60.0)
    )

    assert outcome.llm_spend_usd is None


def test_stderr_tail_keeps_the_last_five_non_empty_lines(tmp_path: Path) -> None:
    runner = KonspektBuildRunner(
        log_dir=tmp_path,
        binary=a_konspekt(
            tmp_path,
            "printf 'Traceback (most recent call last):\\n  frame 1\\n\\n  frame 2\\n"
            "  frame 3\\n\\n  frame 4\\nRuntimeError: notes stage failed\\n' >&2\nexit 1\n",
        ),
    )

    outcome = an_outcome_after_exit(
        runner.start(tmp_path / "HtSuA80QTyo.mkv", tmp_path / "out", "auto", 60.0)
    )

    assert outcome.stderr_tail == (
        "frame 1\nframe 2\nframe 3\nframe 4\nRuntimeError: notes stage failed"
    )


def test_running_build_has_no_outcome_yet(tmp_path: Path) -> None:
    runner = KonspektBuildRunner(log_dir=tmp_path, binary=a_konspekt(tmp_path, "sleep 30\n"))
    build = runner.start(tmp_path / "HtSuA80QTyo.mkv", tmp_path / "out", "auto", 60.0)

    outcome_while_running = build.outcome()
    build.terminate()

    assert outcome_while_running is None


def test_terminate_stops_the_build_process(tmp_path: Path) -> None:
    runner = KonspektBuildRunner(log_dir=tmp_path, binary=a_konspekt(tmp_path, "sleep 30\n"))
    build = runner.start(tmp_path / "HtSuA80QTyo.mkv", tmp_path / "out", "auto", 60.0)

    build.terminate()

    assert an_outcome_after_exit(build).exit_code == -signal.SIGTERM
