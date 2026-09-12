import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

import httpx

from konspekt.pipeline.envelope import STAGES
from konspekt.pipeline.run_config import lecture_slug
from konspekt.worker.application.run_request import RunRequest
from konspekt.worker.application.worker_run import WorkerRun
from konspekt.worker.domain.build_outcome import BuildOutcome
from konspekt.worker.domain.failure_code import FailureCode
from konspekt.worker.domain.secret_values import SecretValues
from konspekt.worker.domain.stored_file import StoredFile
from konspekt.worker.domain.video_metadata import VideoMetadata
from konspekt.worker.ports.outbound.video_unavailable_error import VideoUnavailableError
from konspekt.worker.ports.outbound.worker_api import WorkerApiPort
from konspekt.worker.ports.outbound.worker_api_error import WorkerApiError
from tests.worker.lecture_fixture import write_final_outputs, write_stage_artifact

VIDEO_URL = "https://www.youtube.com/watch?v=HtSuA80QTyo"
RUN_TOKEN = "run-token-sentinel-4b7e91"
PUBLIC_VIDEO = VideoMetadata(
    video_id="HtSuA80QTyo",
    title="Lecture 1: Algorithms and Computation",
    channel="MIT OpenCourseWare",
    duration_seconds=3040.0,
    live_status="not_live",
    availability="public",
)
SUCCESSFUL_BUILD = BuildOutcome(exit_code=0, llm_spend_usd=3.5, stderr_tail="")


class FakeClock:
    def __init__(self) -> None:
        self.current_seconds = 0.0

    def now(self) -> float:
        return self.current_seconds

    def sleep(self, seconds: float) -> None:
        self.current_seconds += seconds


@dataclass(frozen=True)
class SucceededCompletion:
    result: Mapping[str, object]
    files: list[StoredFile]


@dataclass(frozen=True)
class FailedCompletion:
    code: FailureCode
    message: str


@dataclass(frozen=True)
class RecordedUpload:
    name: str
    content_type: str
    content: bytes


class FakeWorkerApi:
    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self.heartbeat_times: list[float] = []
        self.stages: list[str] = []
        self.uploads: list[RecordedUpload] = []
        self.completions: list[SucceededCompletion | FailedCompletion] = []

    def report_heartbeat(self) -> None:
        self.heartbeat_times.append(self._clock.now())

    def report_stage_completed(self, stage: str) -> None:
        self.stages.append(stage)

    def upload(self, name: str, content_type: str, content: bytes) -> str:
        self.uploads.append(RecordedUpload(name, content_type, content))
        return f"storage-{len(self.uploads)}"

    def complete_succeeded(
        self, result: Mapping[str, object], files: Sequence[StoredFile]
    ) -> None:
        self.completions.append(SucceededCompletion(result, list(files)))

    def complete_failed(self, code: FailureCode, message: str) -> None:
        self.completions.append(FailedCompletion(code, message))

    def succeeded(self) -> SucceededCompletion:
        match self.completions:
            case [SucceededCompletion() as completion]:
                return completion
            case _:
                raise AssertionError(f"expected one success completion, got {self.completions}")


class SlowUploadWorkerApi(FakeWorkerApi):
    def upload(self, name: str, content_type: str, content: bytes) -> str:
        self._clock.sleep(25.0)
        return super().upload(name, content_type, content)


class RevokedTokenWorkerApi(FakeWorkerApi):
    def report_heartbeat(self) -> None:
        raise WorkerApiError("worker API events refused the run with HTTP 401")


class RevokedDuringBuildWorkerApi(FakeWorkerApi):
    def report_stage_completed(self, stage: str) -> None:
        if stage in STAGES:
            raise WorkerApiError("worker API events refused the run with HTTP 401")
        super().report_stage_completed(stage)


class UnavailableControlPlane:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(503)


class FakeRunningJob[T]:
    def __init__(self, progress_steps: Sequence[Callable[[], None]], result: T | Exception) -> None:
        self._pending_steps = list(progress_steps)
        self._result = result
        self.is_terminated = False

    def outcome(self) -> T | None:
        if self._pending_steps:
            self._pending_steps.pop(0)()
            return None
        if isinstance(self._result, Exception):
            raise self._result
        return self._result

    def terminate(self) -> None:
        self.is_terminated = True


@dataclass(frozen=True)
class DownloadRequest:
    youtube_url: str
    video_id: str
    dest_dir: Path


class FakeVideoSource:
    def __init__(
        self, metadata: VideoMetadata | VideoUnavailableError, download: FakeRunningJob[Path]
    ) -> None:
        self._metadata = metadata
        self._download = download
        self.metadata_requests: list[str] = []
        self.download_requests: list[DownloadRequest] = []

    def metadata(self, youtube_url: str) -> VideoMetadata:
        self.metadata_requests.append(youtube_url)
        if isinstance(self._metadata, VideoUnavailableError):
            raise self._metadata
        return self._metadata

    def download(self, youtube_url: str, video_id: str, dest_dir: Path) -> FakeRunningJob[Path]:
        self.download_requests.append(DownloadRequest(youtube_url, video_id, dest_dir))
        return self._download


@dataclass(frozen=True)
class BuildRequest:
    video_path: Path
    out_dir: Path
    language: str
    max_llm_usd: float


BuildJobFactory = Callable[[Path], FakeRunningJob[BuildOutcome]]


@dataclass
class FakeBuildRunner:
    job_for_lecture_dir: BuildJobFactory
    requests: list[BuildRequest] = field(default_factory=list)
    started_jobs: list[FakeRunningJob[BuildOutcome]] = field(default_factory=list)

    def start(
        self, video_path: Path, out_dir: Path, language: str, max_llm_usd: float
    ) -> FakeRunningJob[BuildOutcome]:
        self.requests.append(BuildRequest(video_path, out_dir, language, max_llm_usd))
        job = self.job_for_lecture_dir(out_dir / lecture_slug(video_path.name))
        self.started_jobs.append(job)
        return job


def do_nothing() -> None:
    pass


def a_finished_download(work_dir: Path, polls: int = 3) -> FakeRunningJob[Path]:
    return FakeRunningJob([do_nothing] * polls, work_dir / f"{PUBLIC_VIDEO.video_id}.mkv")


def a_video_source(
    work_dir: Path, video: VideoMetadata | VideoUnavailableError = PUBLIC_VIDEO
) -> FakeVideoSource:
    return FakeVideoSource(video, a_finished_download(work_dir))


def lecture_progress(lecture_dir: Path) -> list[Callable[[], None]]:
    return [partial(write_stage_artifact, lecture_dir, stage) for stage in STAGES[:-1]] + [
        partial(write_final_outputs, lecture_dir)
    ]


def a_staged_build(outcome: BuildOutcome = SUCCESSFUL_BUILD) -> FakeBuildRunner:
    return FakeBuildRunner(
        lambda lecture_dir: FakeRunningJob(lecture_progress(lecture_dir), outcome)
    )


def a_build_finished_before_the_first_poll() -> FakeBuildRunner:
    def finished_job(lecture_dir: Path) -> FakeRunningJob[BuildOutcome]:
        for write_progress in lecture_progress(lecture_dir):
            write_progress()
        return FakeRunningJob([], SUCCESSFUL_BUILD)

    return FakeBuildRunner(finished_job)


def a_failing_build(exit_code: int, stderr_tail: str, completed_stages: int = 0) -> FakeBuildRunner:
    outcome = BuildOutcome(exit_code=exit_code, llm_spend_usd=None, stderr_tail=stderr_tail)
    return FakeBuildRunner(
        lambda lecture_dir: FakeRunningJob(
            lecture_progress(lecture_dir)[:completed_stages], outcome
        )
    )


def a_worker_run(
    work_dir: Path,
    clock: FakeClock,
    worker_api: WorkerApiPort,
    video_source: FakeVideoSource,
    build_runner: FakeBuildRunner,
    language: str = "auto",
) -> WorkerRun:
    return WorkerRun(
        video_source=video_source,
        build_runner=build_runner,
        worker_api=worker_api,
        clock=clock,
        secret_values=SecretValues([RUN_TOKEN]),
        request=RunRequest(
            youtube_url=VIDEO_URL, language=language, work_dir=work_dir, max_llm_usd=60.0
        ),
    )


def longest_heartbeat_gap(heartbeat_times: Sequence[float], run_end: float) -> float:
    checkpoints = [0.0, *heartbeat_times, run_end]
    return max(later - earlier for earlier, later in zip(checkpoints, checkpoints[1:]))


def the_only_log_record(records: Sequence[logging.LogRecord]) -> logging.LogRecord:
    match records:
        case [record]:
            return record
        case _:
            raise AssertionError(f"expected one log record, got {records}")
