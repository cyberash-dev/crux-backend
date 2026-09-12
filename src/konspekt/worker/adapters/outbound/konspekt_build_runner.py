import re
import subprocess
from pathlib import Path

from konspekt.worker.adapters.outbound.process_output import error_tail
from konspekt.worker.domain.build_outcome import BuildOutcome
from konspekt.worker.ports.outbound.running_job import RunningJobPort

_TOTAL_SPEND_PATTERN = re.compile(r"^total spend: (\d+(?:\.\d+)?) USD$", re.MULTILINE)
_STDOUT_LOG_NAME = "konspekt-build.stdout.log"
_STDERR_LOG_NAME = "konspekt-build.stderr.log"


class KonspektBuildRunner:
    def __init__(self, log_dir: Path, binary: str = "konspekt") -> None:
        self._log_dir = log_dir
        self._binary = binary

    def start(
        self, video_path: Path, out_dir: Path, language: str, max_llm_usd: float
    ) -> RunningJobPort[BuildOutcome]:
        command = [
            self._binary,
            "build",
            str(video_path),
            "-o",
            str(out_dir),
            "--lang",
            language,
            "--max-llm-usd",
            str(max_llm_usd),
        ]
        stdout_path = self._log_dir / _STDOUT_LOG_NAME
        stderr_path = self._log_dir / _STDERR_LOG_NAME
        with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
            process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=stdout_file, stderr=stderr_file
            )
        return _RunningBuild(process, stdout_path, stderr_path)


class _RunningBuild:
    def __init__(
        self, process: subprocess.Popen[bytes], stdout_path: Path, stderr_path: Path
    ) -> None:
        self._process = process
        self._stdout_path = stdout_path
        self._stderr_path = stderr_path

    def outcome(self) -> BuildOutcome | None:
        exit_code = self._process.poll()
        if exit_code is None:
            return None
        return BuildOutcome(
            exit_code=exit_code,
            llm_spend_usd=_llm_spend_usd(_text(self._stdout_path)),
            stderr_tail=error_tail(_text(self._stderr_path)),
        )

    def terminate(self) -> None:
        self._process.terminate()
        self._process.wait()


def _text(log_path: Path) -> str:
    return log_path.read_text(encoding="utf-8", errors="replace")


def _llm_spend_usd(stdout: str) -> float | None:
    spend_values = _TOTAL_SPEND_PATTERN.findall(stdout)
    return float(spend_values[-1]) if spend_values else None
