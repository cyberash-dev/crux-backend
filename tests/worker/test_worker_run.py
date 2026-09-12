# @covers service:REQ-002
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from konspekt.worker.adapters.outbound.httpx_worker_api import HttpxWorkerApi
from konspekt.worker.domain.failure_code import FailureCode
from konspekt.worker.domain.file_kind import FileKind
from konspekt.worker.domain.stored_file import StoredFile
from konspekt.worker.domain.video_metadata import VideoMetadata
from konspekt.worker.ports.outbound.download_failed_error import DownloadFailedError
from konspekt.worker.ports.outbound.video_unavailable_error import VideoUnavailableError
from konspekt.worker.ports.outbound.worker_api_error import WorkerApiError
from tests.worker.lecture_fixture import (
    FACTCHECK_CLAIMS,
    JPEG_BYTES,
    LECTURE_TITLE,
    MARKDOWN_BYTES,
    NOTES_SECTION,
    PDF_BYTES,
    PNG_BYTES,
    QUIZ_EXPORT,
)
from tests.worker.worker_fakes import (
    PUBLIC_VIDEO,
    RUN_TOKEN,
    VIDEO_URL,
    BuildRequest,
    DownloadRequest,
    FailedCompletion,
    FakeClock,
    FakeRunningJob,
    FakeVideoSource,
    FakeWorkerApi,
    RecordedUpload,
    RevokedDuringBuildWorkerApi,
    RevokedTokenWorkerApi,
    SlowUploadWorkerApi,
    UnavailableControlPlane,
    a_build_finished_before_the_first_poll,
    a_failing_build,
    a_finished_download,
    a_staged_build,
    a_video_source,
    a_worker_run,
    do_nothing,
    longest_heartbeat_gap,
    the_only_log_record,
)

REJECTED_VIDEOS = [
    pytest.param(
        replace(PUBLIC_VIDEO, live_status="is_live", duration_seconds=None),
        "live_status is is_live; only finished recordings are processed",
        id="live",
    ),
    pytest.param(
        replace(PUBLIC_VIDEO, live_status="is_upcoming", duration_seconds=None),
        "live_status is is_upcoming; only finished recordings are processed",
        id="upcoming",
    ),
    pytest.param(
        replace(PUBLIC_VIDEO, live_status="post_live"),
        "live_status is post_live; only finished recordings are processed",
        id="post-live",
    ),
    pytest.param(
        replace(PUBLIC_VIDEO, availability="private"),
        "availability is private; only public videos are processed",
        id="private",
    ),
    pytest.param(
        replace(PUBLIC_VIDEO, availability="unlisted"),
        "availability is unlisted; only public videos are processed",
        id="unlisted",
    ),
    pytest.param(
        replace(PUBLIC_VIDEO, duration_seconds=4 * 3600 + 1.0),
        "duration 14401 s exceeds the 4 h limit",
        id="longer-than-4h",
    ),
    pytest.param(
        replace(PUBLIC_VIDEO, duration_seconds=None),
        "duration is unknown",
        id="unknown-duration",
    ),
]


def test_public_video_reports_download_then_every_pipeline_stage_in_order(
    tmp_path: Path,
) -> None:
    clock = FakeClock()
    worker_api = FakeWorkerApi(clock)
    run = a_worker_run(tmp_path, clock, worker_api, a_video_source(tmp_path), a_staged_build())

    run.execute()

    assert worker_api.stages == [
        "download",
        "ingest",
        "transcription",
        "visual",
        "segmentation",
        "factcheck",
        "notes",
        "quiz",
        "compose",
    ]


def test_success_completion_carries_the_result_built_from_the_artifacts(
    tmp_path: Path,
) -> None:
    clock = FakeClock()
    worker_api = FakeWorkerApi(clock)
    run = a_worker_run(tmp_path, clock, worker_api, a_video_source(tmp_path), a_staged_build())

    run.execute()

    assert worker_api.succeeded().result == {
        "video": {
            "video_id": "HtSuA80QTyo",
            "title": "Lecture 1: Algorithms and Computation",
            "channel": "MIT OpenCourseWare",
            "duration_seconds": 3040.0,
        },
        "outline": {
            "lecture_title": LECTURE_TITLE,
            "sections": [
                {
                    "section_id": "s1",
                    "title": "Course Introduction and Goals",
                    "start_seconds": 0.0,
                    "end_seconds": 179.0,
                    "subsections": [
                        {
                            "section_id": "s1.1",
                            "title": "Instructors and Course Overview",
                            "start_seconds": 0.0,
                            "end_seconds": 48.0,
                            "subsections": [],
                        }
                    ],
                }
            ],
        },
        "sections": [NOTES_SECTION],
        "claims": FACTCHECK_CLAIMS,
        "quiz": QUIZ_EXPORT,
        "cut_log": [
            {
                "start_seconds": 179.0,
                "end_seconds": 201.0,
                "label": "logistics",
                "reason": "problem set deadlines",
            }
        ],
        "llm_spend_usd": 3.5,
    }


def test_success_uploads_the_pdf_the_markdown_and_every_image(tmp_path: Path) -> None:
    clock = FakeClock()
    worker_api = FakeWorkerApi(clock)
    run = a_worker_run(tmp_path, clock, worker_api, a_video_source(tmp_path), a_staged_build())

    run.execute()

    assert worker_api.uploads == [
        RecordedUpload("konspekt.pdf", "application/pdf", PDF_BYTES),
        RecordedUpload("konspekt.md", "text/markdown", MARKDOWN_BYTES),
        RecordedUpload("md/images/frame_125125.jpg", "image/jpeg", JPEG_BYTES),
        RecordedUpload("md/images/illustration_s1.png", "image/png", PNG_BYTES),
    ]


def test_success_completion_lists_every_stored_file(tmp_path: Path) -> None:
    clock = FakeClock()
    worker_api = FakeWorkerApi(clock)
    run = a_worker_run(tmp_path, clock, worker_api, a_video_source(tmp_path), a_staged_build())

    run.execute()

    assert worker_api.succeeded().files == [
        StoredFile(FileKind.PDF, "konspekt.pdf", "storage-1", len(PDF_BYTES), "application/pdf"),
        StoredFile(
            FileKind.MARKDOWN, "konspekt.md", "storage-2", len(MARKDOWN_BYTES), "text/markdown"
        ),
        StoredFile(
            FileKind.IMAGE,
            "md/images/frame_125125.jpg",
            "storage-3",
            len(JPEG_BYTES),
            "image/jpeg",
        ),
        StoredFile(
            FileKind.IMAGE,
            "md/images/illustration_s1.png",
            "storage-4",
            len(PNG_BYTES),
            "image/png",
        ),
    ]


@pytest.mark.parametrize(("video", "reason"), REJECTED_VIDEOS)
def test_rejected_video_fails_with_video_unavailable(
    tmp_path: Path, video: VideoMetadata, reason: str
) -> None:
    clock = FakeClock()
    worker_api = FakeWorkerApi(clock)
    run = a_worker_run(
        tmp_path, clock, worker_api, a_video_source(tmp_path, video), a_staged_build()
    )

    run.execute()

    assert worker_api.completions == [FailedCompletion(FailureCode.VIDEO_UNAVAILABLE, reason)]


@pytest.mark.parametrize(
    "video", [pytest.param(case.values[0], id=case.id) for case in REJECTED_VIDEOS]
)
def test_rejected_video_is_not_downloaded(tmp_path: Path, video: VideoMetadata) -> None:
    clock = FakeClock()
    video_source = a_video_source(tmp_path, video)
    run = a_worker_run(tmp_path, clock, FakeWorkerApi(clock), video_source, a_staged_build())

    run.execute()

    assert video_source.download_requests == []


def test_video_of_exactly_four_hours_is_downloaded(tmp_path: Path) -> None:
    clock = FakeClock()
    video_source = a_video_source(tmp_path, replace(PUBLIC_VIDEO, duration_seconds=4 * 3600.0))
    run = a_worker_run(tmp_path, clock, FakeWorkerApi(clock), video_source, a_staged_build())

    run.execute()

    assert video_source.download_requests == [
        DownloadRequest(VIDEO_URL, PUBLIC_VIDEO.video_id, tmp_path)
    ]


def test_failed_metadata_request_fails_with_video_unavailable(tmp_path: Path) -> None:
    clock = FakeClock()
    worker_api = FakeWorkerApi(clock)
    unavailable = VideoUnavailableError("ERROR: [youtube] HtSuA80QTyo: Video unavailable")
    run = a_worker_run(
        tmp_path, clock, worker_api, a_video_source(tmp_path, unavailable), a_staged_build()
    )

    run.execute()

    assert worker_api.completions == [
        FailedCompletion(
            FailureCode.VIDEO_UNAVAILABLE, "ERROR: [youtube] HtSuA80QTyo: Video unavailable"
        )
    ]


def a_failing_download_source() -> FakeVideoSource:
    download_error = DownloadFailedError("ERROR: unable to download video data: HTTP Error 403")
    return FakeVideoSource(PUBLIC_VIDEO, FakeRunningJob([do_nothing] * 2, download_error))


def test_download_failure_fails_with_download_failed(tmp_path: Path) -> None:
    clock = FakeClock()
    worker_api = FakeWorkerApi(clock)
    run = a_worker_run(tmp_path, clock, worker_api, a_failing_download_source(), a_staged_build())

    run.execute()

    assert worker_api.completions == [
        FailedCompletion(
            FailureCode.DOWNLOAD_FAILED, "ERROR: unable to download video data: HTTP Error 403"
        )
    ]


def test_download_failure_does_not_start_the_build(tmp_path: Path) -> None:
    clock = FakeClock()
    build_runner = a_staged_build()
    run = a_worker_run(
        tmp_path, clock, FakeWorkerApi(clock), a_failing_download_source(), build_runner
    )

    run.execute()

    assert build_runner.requests == []


@pytest.mark.parametrize(
    ("exit_code", "stderr_tail", "expected_completion"),
    [
        pytest.param(
            2,
            "error: missing required env vars: EXA_API_KEY",
            FailedCompletion(
                FailureCode.CONFIGURATION_ERROR, "error: missing required env vars: EXA_API_KEY"
            ),
            id="exit-2",
        ),
        pytest.param(
            1,
            "error: LLM budget exceeded: spent 60.12 of 60.00 USD",
            FailedCompletion(
                FailureCode.PIPELINE_FAILED, "error: LLM budget exceeded: spent 60.12 of 60.00 USD"
            ),
            id="exit-1",
        ),
        pytest.param(
            -9,
            "",
            FailedCompletion(FailureCode.PIPELINE_FAILED, "konspekt build exited with code -9"),
            id="killed-without-stderr",
        ),
    ],
)
def test_failed_build_reports_its_failure_code_and_stderr_tail(
    tmp_path: Path, exit_code: int, stderr_tail: str, expected_completion: FailedCompletion
) -> None:
    clock = FakeClock()
    worker_api = FakeWorkerApi(clock)
    build_runner = a_failing_build(exit_code, stderr_tail, completed_stages=3)
    run = a_worker_run(tmp_path, clock, worker_api, a_video_source(tmp_path), build_runner)

    run.execute()

    assert worker_api.completions == [expected_completion]


def test_build_runs_on_the_downloaded_video_with_language_and_budget(tmp_path: Path) -> None:
    clock = FakeClock()
    build_runner = a_staged_build()
    run = a_worker_run(
        tmp_path, clock, FakeWorkerApi(clock), a_video_source(tmp_path), build_runner, "ru"
    )

    run.execute()

    assert build_runner.requests == [
        BuildRequest(tmp_path / "HtSuA80QTyo.mkv", tmp_path / "out", "ru", 60.0)
    ]


def test_heartbeats_are_never_more_than_60_seconds_apart(tmp_path: Path) -> None:
    clock = FakeClock()
    worker_api = FakeWorkerApi(clock)
    long_download = FakeVideoSource(PUBLIC_VIDEO, a_finished_download(tmp_path, polls=12))
    run = a_worker_run(tmp_path, clock, worker_api, long_download, a_staged_build())

    run.execute()

    assert longest_heartbeat_gap(worker_api.heartbeat_times, clock.now()) <= 60.0


def test_slow_uploads_keep_heartbeats_within_60_seconds(tmp_path: Path) -> None:
    clock = FakeClock()
    worker_api = SlowUploadWorkerApi(clock)
    run = a_worker_run(tmp_path, clock, worker_api, a_video_source(tmp_path), a_staged_build())

    run.execute()

    assert longest_heartbeat_gap(worker_api.heartbeat_times, clock.now()) <= 60.0


def test_rejected_run_token_stops_the_worker_before_reading_metadata(tmp_path: Path) -> None:
    clock = FakeClock()
    video_source = a_video_source(tmp_path)
    run = a_worker_run(
        tmp_path, clock, RevokedTokenWorkerApi(clock), video_source, a_staged_build()
    )

    with pytest.raises(WorkerApiError, match="HTTP 401"):
        run.execute()

    assert video_source.metadata_requests == []


def test_rejected_run_token_during_the_build_terminates_the_build(tmp_path: Path) -> None:
    clock = FakeClock()
    build_runner = a_staged_build()
    run = a_worker_run(
        tmp_path, clock, RevokedDuringBuildWorkerApi(clock), a_video_source(tmp_path), build_runner
    )

    with pytest.raises(WorkerApiError, match="HTTP 401"):
        run.execute()

    assert build_runner.started_jobs[0].is_terminated


def test_failed_completion_masks_the_run_token(tmp_path: Path) -> None:
    clock = FakeClock()
    worker_api = FakeWorkerApi(clock)
    leaking_build = a_failing_build(1, f"LocalProtocolError: Illegal header value b'{RUN_TOKEN}'")
    run = a_worker_run(tmp_path, clock, worker_api, a_video_source(tmp_path), leaking_build)

    run.execute()

    assert worker_api.completions == [
        FailedCompletion(
            FailureCode.PIPELINE_FAILED, "LocalProtocolError: Illegal header value b'***'"
        )
    ]


def test_failure_log_line_never_contains_the_run_token(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clock = FakeClock()
    leaking_build = a_failing_build(1, f"LocalProtocolError: Illegal header value b'{RUN_TOKEN}'")
    run = a_worker_run(
        tmp_path, clock, FakeWorkerApi(clock), a_video_source(tmp_path), leaking_build
    )

    run.execute()

    assert RUN_TOKEN not in str(vars(the_only_log_record(caplog.records)))


def test_stages_written_right_before_the_build_exits_are_reported(tmp_path: Path) -> None:
    clock = FakeClock()
    worker_api = FakeWorkerApi(clock)
    run = a_worker_run(
        tmp_path,
        clock,
        worker_api,
        a_video_source(tmp_path),
        a_build_finished_before_the_first_poll(),
    )

    run.execute()

    assert worker_api.stages == [
        "download",
        "ingest",
        "transcription",
        "visual",
        "segmentation",
        "factcheck",
        "notes",
        "quiz",
        "compose",
    ]


def test_worker_gives_up_after_three_retries_of_a_failing_api_call(tmp_path: Path) -> None:
    clock = FakeClock()
    control_plane = UnavailableControlPlane()
    unavailable_api = HttpxWorkerApi(
        api_base="https://stoic-bird-582.convex.site",
        run_id="k57a1b2c3d4e5f6",
        run_token=RUN_TOKEN,
        http_client=httpx.Client(transport=httpx.MockTransport(control_plane.handler)),
        sleep=clock.sleep,
    )
    video_source = a_video_source(tmp_path)
    run = a_worker_run(tmp_path, clock, unavailable_api, video_source, a_staged_build())

    with pytest.raises(WorkerApiError, match="failed after 4 attempts: HTTP 503"):
        run.execute()

    assert (len(control_plane.requests), clock.now(), video_source.metadata_requests) == (
        4,
        14.0,
        [],
    )
