import json
import subprocess
from collections.abc import Sequence
from pathlib import Path


class FfmpegMediaTools:
    def probe_duration(self, video_path: Path) -> float:
        stdout = _run_media_tool(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(video_path),
            ]
        )
        return float(json.loads(stdout)["format"]["duration"])

    def extract_audio(self, video_path: Path, audio_dest: Path) -> Path:
        _run_media_tool(
            [
                "ffmpeg",
                "-y",
                "-i", str(video_path),
                "-vn",
                "-ac", "1",
                "-ar", "16000",
                "-c:a", "libopus",
                "-b:a", "32k",
                str(audio_dest),
            ]
        )
        return audio_dest


def _run_media_tool(command: Sequence[str]) -> str:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{command[0]} exited with {completed.returncode}: {completed.stderr.strip()}")
    return completed.stdout
