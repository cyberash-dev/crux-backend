# @covers extraction:EXT-002
# @covers extraction:CON-010
# @covers extraction:DLT-010
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from konspekt.features.ingest.adapters.outbound.ffmpeg_tools import FfmpegMediaTools


def a_synthetic_video(directory: Path) -> Path:
    video_path = directory / "lecture.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f", "lavfi", "-i", "testsrc=duration=5:size=320x240:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
            "-shortest",
            str(video_path),
        ],
        capture_output=True,
        check=True,
    )
    return video_path


def test_probe_duration_reports_synthetic_video_length() -> None:
    with tempfile.TemporaryDirectory() as directory:
        video_path = a_synthetic_video(Path(directory))

        duration_seconds = FfmpegMediaTools().probe_duration(video_path)

        assert duration_seconds == pytest.approx(5.0, abs=0.5)


def audio_codec_name(audio_path: Path) -> str:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=codec_name",
            "-of", "json",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return str(json.loads(completed.stdout)["streams"][0]["codec_name"])


def test_extract_audio_writes_non_empty_ogg_opus() -> None:
    with tempfile.TemporaryDirectory() as directory:
        video_path = a_synthetic_video(Path(directory))
        audio_dest = Path(directory) / "audio.ogg"

        extracted_path = FfmpegMediaTools().extract_audio(video_path, audio_dest)

        assert extracted_path == audio_dest
        assert audio_dest.stat().st_size > 0
        assert audio_dest.read_bytes()[:4] == b"OggS"
        assert audio_codec_name(audio_dest) == "opus"


def test_probe_duration_raises_with_stderr_for_missing_file() -> None:
    with pytest.raises(RuntimeError, match="No such file"):
        FfmpegMediaTools().probe_duration(Path("/nonexistent/lecture.mp4"))


def test_extract_audio_raises_with_stderr_for_missing_file() -> None:
    with tempfile.TemporaryDirectory() as directory:
        audio_dest = Path(directory) / "audio.flac"

        with pytest.raises(RuntimeError, match="No such file"):
            FfmpegMediaTools().extract_audio(Path("/nonexistent/lecture.mp4"), audio_dest)
