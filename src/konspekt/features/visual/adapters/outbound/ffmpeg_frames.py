import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

from konspekt.features.visual.domain.frame import ContentBox, VisualConfig

_PTS_TIME_PATTERN = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")


class FfmpegFrameCapture:
    def __init__(self, binary_name: str = "ffmpeg") -> None:
        self._binary_name = binary_name

    def capture_candidates(
        self,
        video_path: Path,
        frames_dir: Path,
        config: VisualConfig,
        content_box: ContentBox | None,
    ) -> list[tuple[float, Path]]:
        frames_dir.mkdir(parents=True, exist_ok=True)
        crop_prefix = "" if content_box is None else f"{_crop_filter(content_box)},"
        passes = (
            ("scene", f"{crop_prefix}select='gt(scene,{config.scene_threshold})',showinfo"),
            (
                "interval",
                f"{crop_prefix}select='isnan(prev_selected_t)"
                f"+gte(t-prev_selected_t,{config.sampling_interval_seconds})',showinfo",
            ),
        )
        frames_by_ms: dict[int, Path] = {}
        for prefix, filter_expression in passes:
            timestamps = self._run_capture_pass(
                video_path, frames_dir, prefix, filter_expression
            )
            for frame_number, timestamp in enumerate(timestamps, start=1):
                source_path = frames_dir / f"{prefix}_{frame_number:06d}.jpg"
                milliseconds = round(timestamp * 1000)
                if milliseconds in frames_by_ms:
                    source_path.unlink()
                    continue
                target_path = frames_dir / f"frame_{milliseconds}.jpg"
                source_path.rename(target_path)
                frames_by_ms[milliseconds] = target_path
        return [
            (milliseconds / 1000, path)
            for milliseconds, path in sorted(frames_by_ms.items())
        ]

    def capture_probes(
        self, video_path: Path, probes_dir: Path, timestamps: Sequence[float]
    ) -> list[Path]:
        probes_dir.mkdir(parents=True, exist_ok=True)
        probe_paths: list[Path] = []
        for index, timestamp in enumerate(timestamps):
            probe_path = probes_dir / f"probe_{index:03d}.jpg"
            command = [
                self._binary_name,
                "-hide_banner",
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                str(probe_path),
            ]
            completed = subprocess.run(command, capture_output=True, text=True)
            if completed.returncode != 0:
                raise RuntimeError(
                    f"ffmpeg probe at {timestamp:.3f}s failed for {video_path}: "
                    f"{completed.stderr}"
                )
            probe_paths.append(probe_path)
        return probe_paths

    def _run_capture_pass(
        self, video_path: Path, frames_dir: Path, prefix: str, filter_expression: str
    ) -> list[float]:
        command = [
            self._binary_name,
            "-hide_banner",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            filter_expression,
            "-fps_mode",
            "vfr",
            "-pix_fmt",
            "yuvj420p",
            str(frames_dir / f"{prefix}_%06d.jpg"),
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(
                f"ffmpeg {prefix} pass failed for {video_path}: {completed.stderr}"
            )
        return [float(value) for value in _PTS_TIME_PATTERN.findall(completed.stderr)]


def _crop_filter(content_box: ContentBox) -> str:
    return (
        f"crop={content_box.width}:{content_box.height}:{content_box.x}:{content_box.y}"
    )
