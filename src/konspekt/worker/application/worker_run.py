import logging
from collections.abc import Callable
from pathlib import Path

from konspekt.pipeline.envelope import STAGES
from konspekt.pipeline.run_config import lecture_slug
from konspekt.pipeline.stage_runner import ArtifactStore
from konspekt.worker.application.deliverables import deliverables
from konspekt.worker.application.run_request import RunRequest
from konspekt.worker.application.run_result import run_result
from konspekt.worker.domain.build_outcome import BuildOutcome
from konspekt.worker.domain.deliverable import Deliverable
from konspekt.worker.domain.failure_code import FailureCode
from konspekt.worker.domain.secret_values import SecretValues
from konspekt.worker.domain.stored_file import StoredFile
from konspekt.worker.domain.video_metadata import VideoMetadata
from konspekt.worker.ports.outbound.build_runner import BuildRunnerPort
from konspekt.worker.ports.outbound.clock import ClockPort
from konspekt.worker.ports.outbound.download_failed_error import DownloadFailedError
from konspekt.worker.ports.outbound.running_job import RunningJobPort
from konspekt.worker.ports.outbound.video_source import VideoSourcePort
from konspekt.worker.ports.outbound.video_unavailable_error import VideoUnavailableError
from konspekt.worker.ports.outbound.worker_api import WorkerApiPort
from konspekt.worker.ports.outbound.worker_api_error import WorkerApiError

_DOWNLOAD_STAGE = "download"
_POLL_INTERVAL_SECONDS = 10.0
_HEARTBEAT_INTERVAL_SECONDS = 30.0
_OUT_DIR_NAME = "out"

_logger = logging.getLogger(__name__)


class _RunFailure(Exception):
    def __init__(self, code: FailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class WorkerRun:
    def __init__(
        self,
        video_source: VideoSourcePort,
        build_runner: BuildRunnerPort,
        worker_api: WorkerApiPort,
        clock: ClockPort,
        secret_values: SecretValues,
        request: RunRequest,
    ) -> None:
        self._video_source = video_source
        self._build_runner = build_runner
        self._worker_api = worker_api
        self._clock = clock
        self._secret_values = secret_values
        self._request = request
        self._out_dir = request.work_dir / _OUT_DIR_NAME
        self._reported_stages: set[str] = set()
        self._last_heartbeat_at = float("-inf")

    def execute(self) -> None:
        self._send_heartbeat()
        try:
            video = self._accepted_video()
            video_path = self._downloaded_video(video.video_id)
            self._report_stage(_DOWNLOAD_STAGE)
            slug = lecture_slug(video_path.name)
            build_outcome = self._successful_build(video_path, slug)
        except _RunFailure as failure:
            self._complete_failed(failure)
            return
        self._complete_succeeded(video, slug, build_outcome.llm_spend_usd)

    def _accepted_video(self) -> VideoMetadata:
        try:
            video = self._video_source.metadata(self._request.youtube_url)
        except VideoUnavailableError as error:
            raise _RunFailure(FailureCode.VIDEO_UNAVAILABLE, str(error)) from error
        rejection_reason = video.rejection_reason()
        if rejection_reason is not None:
            raise _RunFailure(FailureCode.VIDEO_UNAVAILABLE, rejection_reason)
        return video

    def _downloaded_video(self, video_id: str) -> Path:
        try:
            download = self._video_source.download(
                self._request.youtube_url, video_id, self._request.work_dir
            )
            return self._awaited_outcome(download, self._send_heartbeat_if_due)
        except DownloadFailedError as error:
            raise _RunFailure(FailureCode.DOWNLOAD_FAILED, str(error)) from error

    def _successful_build(self, video_path: Path, slug: str) -> BuildOutcome:
        stage_store = ArtifactStore(self._out_dir / slug / "work")
        build = self._build_runner.start(
            video_path, self._out_dir, self._request.language, self._request.max_llm_usd
        )
        build_outcome = self._awaited_outcome(
            build, lambda: self._report_build_progress(stage_store)
        )
        self._report_new_stages(stage_store)
        failure_code = build_outcome.failure_code()
        if failure_code is not None:
            raise _RunFailure(
                failure_code,
                build_outcome.stderr_tail
                or f"konspekt build exited with code {build_outcome.exit_code}",
            )
        return build_outcome

    def _complete_succeeded(
        self, video: VideoMetadata, slug: str, llm_spend_usd: float | None
    ) -> None:
        result = run_result(self._out_dir, slug, video, llm_spend_usd)
        stored_files = [
            self._stored_file(deliverable) for deliverable in deliverables(self._out_dir / slug)
        ]
        self._worker_api.complete_succeeded(result, stored_files)

    def _stored_file(self, deliverable: Deliverable) -> StoredFile:
        content = deliverable.path.read_bytes()
        storage_id = self._worker_api.upload(deliverable.name, deliverable.content_type, content)
        self._send_heartbeat_if_due()
        return StoredFile(
            kind=deliverable.kind,
            name=deliverable.name,
            storage_id=storage_id,
            size_bytes=len(content),
            content_type=deliverable.content_type,
        )

    def _complete_failed(self, failure: _RunFailure) -> None:
        message = self._secret_values.masked(failure.message)
        _logger.warning("worker.run_failed", extra={"code": failure.code.value, "detail": message})
        self._worker_api.complete_failed(failure.code, message)

    def _awaited_outcome[T](self, job: RunningJobPort[T], on_poll: Callable[[], None]) -> T:
        try:
            outcome = job.outcome()
            while outcome is None:
                self._clock.sleep(_POLL_INTERVAL_SECONDS)
                on_poll()
                outcome = job.outcome()
            return outcome
        except WorkerApiError:
            job.terminate()
            raise

    def _report_build_progress(self, stage_store: ArtifactStore) -> None:
        self._report_new_stages(stage_store)
        self._send_heartbeat_if_due()

    def _report_new_stages(self, stage_store: ArtifactStore) -> None:
        for stage in STAGES:
            if stage not in self._reported_stages and stage_store.path_for(stage).exists():
                self._report_stage(stage)

    def _report_stage(self, stage: str) -> None:
        self._worker_api.report_stage_completed(stage)
        self._reported_stages.add(stage)

    def _send_heartbeat_if_due(self) -> None:
        if self._clock.now() - self._last_heartbeat_at >= _HEARTBEAT_INTERVAL_SECONDS:
            self._send_heartbeat()

    def _send_heartbeat(self) -> None:
        self._worker_api.report_heartbeat()
        self._last_heartbeat_at = self._clock.now()
