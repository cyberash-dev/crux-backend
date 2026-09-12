import stat
import time
from pathlib import Path

from konspekt.worker.ports.outbound.running_job import RunningJobPort

_EXIT_TIMEOUT_SECONDS = 10.0
_POLL_SECONDS = 0.01


def a_stub_executable(tmp_path: Path, name: str, body: str) -> str:
    script_path = tmp_path / name
    script_path.write_text("#!/bin/sh\n" + body)
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)
    return str(script_path)


def recording_arguments_to(args_log_path: Path) -> str:
    return f'printf "%s\\n" "$@" > "{args_log_path}"\n'


def an_outcome_after_exit[T](job: RunningJobPort[T]) -> T:
    deadline = time.monotonic() + _EXIT_TIMEOUT_SECONDS
    outcome = job.outcome()
    while outcome is None:
        if time.monotonic() > deadline:
            raise AssertionError("stub process did not exit in time")
        time.sleep(_POLL_SECONDS)
        outcome = job.outcome()
    return outcome
