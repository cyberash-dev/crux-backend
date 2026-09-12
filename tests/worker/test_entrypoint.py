# @covers service:REQ-002
from pathlib import Path

import pytest

from konspekt.worker.entrypoint import run_worker

RUN_TOKEN = "run-token-sentinel-2f6c0d"


def an_environment(work_dir: Path, **overrides: str) -> dict[str, str]:
    return {
        "KONSPEKT_RUN_ID": "k57a1b2c3d4e5f6",
        "KONSPEKT_API_BASE": "https://stoic-bird-582.convex.site",
        "KONSPEKT_RUN_TOKEN": RUN_TOKEN,
        "KONSPEKT_YOUTUBE_URL": "https://www.youtube.com/watch?v=HtSuA80QTyo",
        "KONSPEKT_LANG": "auto",
        "KONSPEKT_WORK_DIR": str(work_dir),
        **overrides,
    }


def test_missing_required_env_vars_exit_with_code_2(tmp_path: Path) -> None:
    exit_code = run_worker(an_environment(tmp_path, KONSPEKT_YOUTUBE_URL="", KONSPEKT_LANG=""))

    assert exit_code == 2


def test_missing_required_env_vars_are_named_without_any_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_worker(an_environment(tmp_path, KONSPEKT_YOUTUBE_URL="", KONSPEKT_LANG=""))

    assert capsys.readouterr().err == (
        "error: missing required env vars: KONSPEKT_YOUTUBE_URL, KONSPEKT_LANG\n"
    )


def test_non_numeric_llm_budget_exits_with_code_2(tmp_path: Path) -> None:
    exit_code = run_worker(an_environment(tmp_path, KONSPEKT_MAX_LLM_USD="sixty"))

    assert exit_code == 2
