import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from konspekt.features.visual.adapters.outbound.ffmpeg_frames import FfmpegFrameCapture
from konspekt.features.visual.domain.frame import ContentBox, VisualConfig

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg binary is not on PATH"
)


def a_video_with_scene_change(path: Path) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x120:d=3:r=10",
            "-f",
            "lavfi",
            "-i",
            "color=c=white:s=160x120:d=3:r=10",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def a_static_limited_range_video(path: Path) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=gray:s=160x120:d=3:r=10",
            "-pix_fmt",
            "yuv420p",
            "-color_range",
            "tv",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


@requires_ffmpeg
def test_capture_without_scene_change_returns_interval_frames(tmp_path: Path) -> None:
    """# @covers extraction:EXT-002"""
    video_path = a_static_limited_range_video(tmp_path / "lecture.mp4")
    frames_dir = tmp_path / "frames"

    candidates = FfmpegFrameCapture().capture_candidates(
        video_path, frames_dir, VisualConfig(), None
    )

    assert [timestamp for timestamp, _ in candidates] == [0.0]


@requires_ffmpeg
def test_capture_finds_scene_change_and_interval_frames(tmp_path: Path) -> None:
    """# @covers extraction:EXT-002"""
    video_path = a_video_with_scene_change(tmp_path / "lecture.mp4")
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()

    candidates = FfmpegFrameCapture().capture_candidates(
        video_path, frames_dir, VisualConfig(), None
    )

    timestamps = [timestamp for timestamp, _ in candidates]
    assert len(candidates) >= 2
    assert timestamps == sorted(timestamps)
    assert any(2.0 <= timestamp <= 4.0 for timestamp in timestamps)
    assert all(image_path.exists() for _, image_path in candidates)
    assert all(image_path.name.startswith("frame_") for _, image_path in candidates)
    assert all(image_path.suffix == ".jpg" for _, image_path in candidates)


@requires_ffmpeg
def test_missing_input_raises_error_with_ffmpeg_stderr(tmp_path: Path) -> None:
    """# @covers extraction:EXT-002"""
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()

    with pytest.raises(RuntimeError, match="No such file"):
        FfmpegFrameCapture().capture_candidates(
            tmp_path / "absent.mp4", frames_dir, VisualConfig(), None
        )


@requires_ffmpeg
def test_creates_missing_frames_dir(tmp_path: Path) -> None:
    video = a_video_with_scene_change(tmp_path / "scene.mp4")
    absent_dir = tmp_path / "work" / "frames"

    candidates = FfmpegFrameCapture().capture_candidates(video, absent_dir, VisualConfig(), None)

    assert absent_dir.is_dir()
    assert candidates


@requires_ffmpeg
def test_capture_probes_writes_one_full_size_frame_per_timestamp(tmp_path: Path) -> None:
    """# @covers extraction:REQ-011"""
    video_path = a_video_with_scene_change(tmp_path / "lecture.mp4")
    probes_dir = tmp_path / "work" / "probes"

    probe_paths = FfmpegFrameCapture().capture_probes(video_path, probes_dir, [0.5, 2.5, 4.5])

    assert [path.name for path in probe_paths] == ["probe_000.jpg", "probe_001.jpg", "probe_002.jpg"]
    assert all(path.parent == probes_dir for path in probe_paths)
    assert [Image.open(path).size for path in probe_paths] == [(160, 120)] * 3


@requires_ffmpeg
def test_capture_with_content_box_stores_cropped_frames(tmp_path: Path) -> None:
    """# @covers extraction:REQ-011"""
    video_path = a_video_with_scene_change(tmp_path / "lecture.mp4")
    frames_dir = tmp_path / "frames"

    candidates = FfmpegFrameCapture().capture_candidates(
        video_path, frames_dir, VisualConfig(), ContentBox(x=10, y=20, width=100, height=60)
    )

    assert candidates
    assert {Image.open(path).size for _, path in candidates} == {(100, 60)}
