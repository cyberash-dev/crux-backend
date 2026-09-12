from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from konspekt.features.visual.domain.frame import ContentBox, VisualConfig


class FrameCapturePort(Protocol):
    def capture_candidates(
        self,
        video_path: Path,
        frames_dir: Path,
        config: VisualConfig,
        content_box: ContentBox | None,
    ) -> list[tuple[float, Path]]:
        """Returns (timestamp_seconds, image_path) pairs, unsorted, pre-dedupe;
        with a content_box every stored candidate is cropped to it and scene
        detection runs on the cropped picture (extraction:REQ-011)."""
        ...

    def capture_probes(
        self, video_path: Path, probes_dir: Path, timestamps: Sequence[float]
    ) -> list[Path]:
        """Full-size (uncropped) frames at the given timestamps, in order."""
        ...


class LayoutDetectionPort(Protocol):
    def detect_content_box(self, probe_paths: Sequence[Path]) -> ContentBox | None:
        """Lecture content region shared by the probe frames, in source pixels;
        None when undetectable (extraction:EXT-005). Never raises on provider
        failure."""
        ...


class OcrPort(Protocol):
    def read_text(self, image_path: Path) -> str | None: ...
