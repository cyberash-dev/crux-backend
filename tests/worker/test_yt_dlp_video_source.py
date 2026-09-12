# @covers service:EXT-002
import json
from pathlib import Path

import pytest

from konspekt.worker.adapters.outbound.yt_dlp_video_source import YtDlpVideoSource
from konspekt.worker.domain.video_metadata import VideoMetadata
from konspekt.worker.ports.outbound.download_failed_error import DownloadFailedError
from konspekt.worker.ports.outbound.video_unavailable_error import VideoUnavailableError
from tests.worker.stub_processes import (
    a_stub_executable,
    an_outcome_after_exit,
    recording_arguments_to,
)

VIDEO_URL = "https://www.youtube.com/watch?v=HtSuA80QTyo"
PROXY_URL = "http://proxy-user:proxy-pass@proxy.example:8080"


def a_metadata_fixture(**overrides: object) -> dict[str, object]:
    return {
        "id": "HtSuA80QTyo",
        "title": "Lecture 1: Algorithms and Computation",
        "channel": "MIT OpenCourseWare",
        "uploader": "MIT OpenCourseWare",
        "duration": 3040,
        "live_status": "not_live",
        "availability": "public",
        "age_limit": 0,
        **overrides,
    }


def a_metadata_yt_dlp(tmp_path: Path, fixture: dict[str, object], args_log_path: Path) -> str:
    fixture_path = tmp_path / "metadata.json"
    fixture_path.write_text(json.dumps(fixture))
    return a_stub_executable(
        tmp_path, "yt-dlp", recording_arguments_to(args_log_path) + f'cat "{fixture_path}"\n'
    )


def test_metadata_command_restricts_yt_dlp_to_youtube_through_the_proxy(tmp_path: Path) -> None:
    args_log_path = tmp_path / "args.log"
    source = YtDlpVideoSource(
        proxy_url=PROXY_URL,
        binary=a_metadata_yt_dlp(tmp_path, a_metadata_fixture(), args_log_path),
    )

    source.metadata(VIDEO_URL)

    assert args_log_path.read_text().splitlines() == [
        "--proxy",
        PROXY_URL,
        "--ies",
        "youtube",
        "--no-playlist",
        "--ignore-config",
        "--no-remote-components",
        "-J",
        VIDEO_URL,
    ]


def test_metadata_command_has_no_proxy_option_without_a_proxy(tmp_path: Path) -> None:
    args_log_path = tmp_path / "args.log"
    source = YtDlpVideoSource(
        proxy_url=None, binary=a_metadata_yt_dlp(tmp_path, a_metadata_fixture(), args_log_path)
    )

    source.metadata(VIDEO_URL)

    assert args_log_path.read_text().splitlines() == [
        "--ies",
        "youtube",
        "--no-playlist",
        "--ignore-config",
        "--no-remote-components",
        "-J",
        VIDEO_URL,
    ]


def test_public_metadata_fixture_maps_to_video_metadata(tmp_path: Path) -> None:
    source = YtDlpVideoSource(
        proxy_url=PROXY_URL,
        binary=a_metadata_yt_dlp(tmp_path, a_metadata_fixture(), tmp_path / "args.log"),
    )

    video = source.metadata(VIDEO_URL)

    assert video == VideoMetadata(
        video_id="HtSuA80QTyo",
        title="Lecture 1: Algorithms and Computation",
        channel="MIT OpenCourseWare",
        duration_seconds=3040.0,
        live_status="not_live",
        availability="public",
    )


@pytest.mark.parametrize(
    ("fixture", "reason"),
    [
        pytest.param(
            a_metadata_fixture(live_status="is_live", duration=None),
            "live_status is is_live; only finished recordings are processed",
            id="live",
        ),
        pytest.param(
            a_metadata_fixture(live_status="is_upcoming", duration=None, availability=None),
            "live_status is is_upcoming; only finished recordings are processed",
            id="upcoming",
        ),
        pytest.param(
            a_metadata_fixture(availability="private"),
            "availability is private; only public videos are processed",
            id="private",
        ),
    ],
)
def test_live_upcoming_or_private_fixture_is_rejected(
    tmp_path: Path, fixture: dict[str, object], reason: str
) -> None:
    source = YtDlpVideoSource(
        proxy_url=PROXY_URL, binary=a_metadata_yt_dlp(tmp_path, fixture, tmp_path / "args.log")
    )

    video = source.metadata(VIDEO_URL)

    assert video.rejection_reason() == reason


def test_failed_metadata_command_raises_video_unavailable_with_its_stderr(tmp_path: Path) -> None:
    source = YtDlpVideoSource(
        proxy_url=PROXY_URL,
        binary=a_stub_executable(
            tmp_path,
            "yt-dlp",
            "echo \"ERROR: [youtube] HtSuA80QTyo: Private video. Sign in if you've been granted"
            ' access to this video" >&2\nexit 1\n',
        ),
    )

    with pytest.raises(VideoUnavailableError, match="HtSuA80QTyo: Private video"):
        source.metadata(VIDEO_URL)


@pytest.mark.parametrize(
    ("stdout", "message"),
    [
        pytest.param("not json at all", "not valid JSON", id="not-json"),
        pytest.param(json.dumps(["HtSuA80QTyo"]), "not a JSON object", id="not-an-object"),
        pytest.param(json.dumps(a_metadata_fixture(title=None)), "lacks 'title'", id="no-title"),
        pytest.param(
            json.dumps(a_metadata_fixture(duration="50:40")), "'duration' is not a number",
            id="text-duration",
        ),
        pytest.param(
            json.dumps(a_metadata_fixture(id="../../etc/passwd")), "unexpected id",
            id="path-like-id",
        ),
    ],
)
def test_malformed_metadata_raises_video_unavailable(
    tmp_path: Path, stdout: str, message: str
) -> None:
    stdout_path = tmp_path / "stdout.txt"
    stdout_path.write_text(stdout)
    source = YtDlpVideoSource(
        proxy_url=None, binary=a_stub_executable(tmp_path, "yt-dlp", f'cat "{stdout_path}"\n')
    )

    with pytest.raises(VideoUnavailableError, match=message):
        source.metadata(VIDEO_URL)


def a_downloading_yt_dlp(tmp_path: Path, args_log_path: Path) -> str:
    return a_stub_executable(
        tmp_path,
        "yt-dlp",
        recording_arguments_to(args_log_path) + f'printf "mkv" > "{tmp_path}/HtSuA80QTyo.mkv"\n',
    )


def test_download_command_fetches_https_1080p_merged_into_mkv_through_the_proxy(
    tmp_path: Path,
) -> None:
    args_log_path = tmp_path / "args.log"
    source = YtDlpVideoSource(
        proxy_url=PROXY_URL, binary=a_downloading_yt_dlp(tmp_path, args_log_path)
    )

    an_outcome_after_exit(source.download(VIDEO_URL, "HtSuA80QTyo", tmp_path))

    assert args_log_path.read_text().splitlines() == [
        "--proxy",
        PROXY_URL,
        "--ies",
        "youtube",
        "--no-playlist",
        "--ignore-config",
        "--no-remote-components",
        "--no-progress",
        "-f",
        "bv*[height<=1080][vcodec^=vp9][protocol=https]+ba/bv*[height<=1080][protocol=https]+ba",
        "--merge-output-format",
        "mkv",
        "-o",
        f"{tmp_path}/HtSuA80QTyo.%(ext)s",
        VIDEO_URL,
    ]


def test_finished_download_yields_the_merged_mkv(tmp_path: Path) -> None:
    source = YtDlpVideoSource(
        proxy_url=PROXY_URL, binary=a_downloading_yt_dlp(tmp_path, tmp_path / "args.log")
    )

    video_path = an_outcome_after_exit(source.download(VIDEO_URL, "HtSuA80QTyo", tmp_path))

    assert video_path == tmp_path / "HtSuA80QTyo.mkv"


def test_running_download_has_no_outcome_yet(tmp_path: Path) -> None:
    source = YtDlpVideoSource(
        proxy_url=PROXY_URL, binary=a_stub_executable(tmp_path, "yt-dlp", "sleep 30\n")
    )
    download = source.download(VIDEO_URL, "HtSuA80QTyo", tmp_path)

    outcome_while_running = download.outcome()
    download.terminate()

    assert outcome_while_running is None


def test_failed_download_raises_download_failed_with_its_stderr(tmp_path: Path) -> None:
    source = YtDlpVideoSource(
        proxy_url=PROXY_URL,
        binary=a_stub_executable(
            tmp_path,
            "yt-dlp",
            'echo "ERROR: unable to download video data: HTTP Error 403: Forbidden" >&2\nexit 1\n',
        ),
    )
    download = source.download(VIDEO_URL, "HtSuA80QTyo", tmp_path)

    with pytest.raises(DownloadFailedError, match="HTTP Error 403: Forbidden"):
        an_outcome_after_exit(download)


def test_download_without_the_merged_file_raises_download_failed(tmp_path: Path) -> None:
    source = YtDlpVideoSource(
        proxy_url=PROXY_URL, binary=a_stub_executable(tmp_path, "yt-dlp", "exit 0\n")
    )
    download = source.download(VIDEO_URL, "HtSuA80QTyo", tmp_path)

    with pytest.raises(DownloadFailedError, match="without writing HtSuA80QTyo.mkv"):
        an_outcome_after_exit(download)
