from pathlib import Path
from typing import Protocol

from konspekt.worker.domain.build_outcome import BuildOutcome
from konspekt.worker.ports.outbound.running_job import RunningJobPort


class BuildRunnerPort(Protocol):
    def start(
        self, video_path: Path, out_dir: Path, language: str, max_llm_usd: float
    ) -> RunningJobPort[BuildOutcome]: ...
