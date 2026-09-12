import json
import re
import subprocess
from pathlib import Path

from konspekt.worker.adapters.outbound.process_output import error_tail
from konspekt.worker.domain.video_metadata import VideoMetadata
from konspekt.worker.ports.outbound.download_failed_error import DownloadFailedError
from konspekt.worker.ports.outbound.running_job import RunningJobPort
from konspekt.worker.ports.outbound.video_unavailable_error import VideoUnavailableError

_VIDEO_FORMAT = (
    "bv*[height<=1080][vcodec^=vp9][protocol=https]+ba/bv*[height<=1080][protocol=https]+ba"
)
_MERGED_EXTENSION = "mkv"
_DOWNLOAD_LOG_NAME = "yt-dlp-download.log"
_VIDEO_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


class YtDlpVideoSource:
    def __init__(self, proxy_url: str | None, binary: str = "yt-dlp") -> None:
        self._proxy_url = proxy_url
        self._binary = binary

    def metadata(self, youtube_url: str) -> VideoMetadata:
        completed = subprocess.run(
            [*self._youtube_command(), "-J", youtube_url],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise VideoUnavailableError(
                error_tail(completed.stderr) or f"yt-dlp exited with code {completed.returncode}"
            )
        return _video_metadata(completed.stdout)

    def download(self, youtube_url: str, video_id: str, dest_dir: Path) -> RunningJobPort[Path]:
        log_path = dest_dir / _DOWNLOAD_LOG_NAME
        command = [
            *self._youtube_command(),
            "--no-progress",
            "-f",
            _VIDEO_FORMAT,
            "--merge-output-format",
            _MERGED_EXTENSION,
            "-o",
            str(dest_dir / f"{video_id}.%(ext)s"),
            youtube_url,
        ]
        with log_path.open("wb") as log_file:
            process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log_file
            )
        return _RunningDownload(process, log_path, dest_dir / f"{video_id}.{_MERGED_EXTENSION}")

    def _youtube_command(self) -> list[str]:
        proxy_options = ["--proxy", self._proxy_url] if self._proxy_url else []
        return [
            self._binary,
            *proxy_options,
            "--ies",
            "youtube",
            "--no-playlist",
            "--ignore-config",
            "--no-remote-components",
        ]


class _RunningDownload:
    def __init__(
        self, process: subprocess.Popen[bytes], log_path: Path, video_path: Path
    ) -> None:
        self._process = process
        self._log_path = log_path
        self._video_path = video_path

    def outcome(self) -> Path | None:
        exit_code = self._process.poll()
        if exit_code is None:
            return None
        if exit_code != 0:
            stderr = self._log_path.read_text(encoding="utf-8", errors="replace")
            raise DownloadFailedError(error_tail(stderr) or f"yt-dlp exited with code {exit_code}")
        if not self._video_path.is_file():
            raise DownloadFailedError(f"yt-dlp finished without writing {self._video_path.name}")
        return self._video_path

    def terminate(self) -> None:
        self._process.terminate()
        self._process.wait()


def _video_metadata(raw_json: str) -> VideoMetadata:
    try:
        info = json.loads(raw_json)
    except json.JSONDecodeError as error:
        raise VideoUnavailableError(f"yt-dlp metadata is not valid JSON: {error}") from error
    if not isinstance(info, dict):
        raise VideoUnavailableError("yt-dlp metadata is not a JSON object")
    video_id = _required_text(info, "id")
    if _VIDEO_ID_PATTERN.fullmatch(video_id) is None:
        raise VideoUnavailableError(f"yt-dlp metadata carries an unexpected id {video_id!r}")
    return VideoMetadata(
        video_id=video_id,
        title=_required_text(info, "title"),
        channel=_required_text(info, "channel"),
        duration_seconds=_optional_number(info, "duration"),
        live_status=_optional_text(info, "live_status"),
        availability=_optional_text(info, "availability"),
    )


def _required_text(info: dict[str, object], key: str) -> str:
    value = info.get(key)
    if not isinstance(value, str) or not value:
        raise VideoUnavailableError(f"yt-dlp metadata lacks {key!r}")
    return value


def _optional_text(info: dict[str, object], key: str) -> str | None:
    value = info.get(key)
    if value is not None and not isinstance(value, str):
        raise VideoUnavailableError(f"yt-dlp metadata field {key!r} is not text")
    return value


def _optional_number(info: dict[str, object], key: str) -> float | None:
    value = info.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise VideoUnavailableError(f"yt-dlp metadata field {key!r} is not a number")
    return float(value)
