import logging
from collections.abc import Sequence
from pathlib import Path

from PIL import Image

from konspekt.features.visual.application.dedupe import dedupe_frames
from konspekt.features.visual.application.dhash import compute_dhash
from konspekt.features.visual.domain.frame import (
    ContentBox,
    Frame,
    FrameExtraction,
    VisualConfig,
)
from konspekt.features.visual.ports.outbound.frame_tools import (
    FrameCapturePort,
    LayoutDetectionPort,
    OcrPort,
)

_logger = logging.getLogger(__name__)
_PROBE_SPAN_START_PERCENT = 10
_PROBE_SPAN_END_PERCENT = 90


def extract_frames(
    video_path: Path,
    frames_dir: Path,
    config: VisualConfig,
    capture: FrameCapturePort,
    ocr: OcrPort,
    layout: LayoutDetectionPort,
    duration_seconds: float,
) -> FrameExtraction:
    probe_paths = capture.capture_probes(
        video_path, frames_dir / "probes", probe_timestamps(duration_seconds, config.probe_count)
    )
    content_box = _accepted_content_box(probe_paths, config, layout)
    candidates = capture.capture_candidates(video_path, frames_dir, config, content_box)
    hashed_candidates = {
        timestamp: (image_path, compute_dhash(image_path))
        for timestamp, image_path in candidates
    }
    survivors = dedupe_frames(
        [(timestamp, dhash) for timestamp, (_, dhash) in hashed_candidates.items()],
        config,
    )
    frames = []
    for timestamp, dhash in survivors:
        image_path, _ = hashed_candidates[timestamp]
        frames.append(
            Frame(
                timestamp_seconds=timestamp,
                image_path=image_path,
                dhash=dhash,
                ocr_text=ocr.read_text(image_path),
            )
        )
    return FrameExtraction(frames=tuple(frames), content_box=content_box)


def probe_timestamps(duration_seconds: float, probe_count: int) -> list[float]:
    if probe_count <= 0 or duration_seconds <= 0:
        return []
    if probe_count == 1:
        midpoint_percent = (_PROBE_SPAN_START_PERCENT + _PROBE_SPAN_END_PERCENT) / 2
        return [duration_seconds * midpoint_percent / 100]
    step_percent = (_PROBE_SPAN_END_PERCENT - _PROBE_SPAN_START_PERCENT) / (probe_count - 1)
    return [
        duration_seconds * (_PROBE_SPAN_START_PERCENT + step_percent * index) / 100
        for index in range(probe_count)
    ]


def _accepted_content_box(
    probe_paths: Sequence[Path], config: VisualConfig, layout: LayoutDetectionPort
) -> ContentBox | None:
    if not probe_paths:
        _logger.warning("visual.layout_skipped", extra={"reason": "no_probes"})
        return None
    try:
        detected_box = layout.detect_content_box(probe_paths)
    except Exception as error:
        _logger.warning(
            "visual.layout_detection_failed",
            extra={"reason": "port_error", "error": str(error)},
        )
        return None
    if detected_box is None:
        _logger.warning("visual.layout_skipped", extra={"reason": "no_box_detected"})
        return None
    with Image.open(probe_paths[0]) as probe_image:
        frame_width, frame_height = probe_image.size
    if not detected_box.fits_inside(frame_width, frame_height):
        _logger.warning(
            "visual.content_box_rejected",
            extra={
                "reason": "outside_frame",
                "frame_width": frame_width,
                "frame_height": frame_height,
                "box": detected_box,
            },
        )
        return None
    area_share = detected_box.area_share(frame_width, frame_height)
    if area_share < config.min_content_area_share:
        _logger.warning(
            "visual.content_box_rejected",
            extra={
                "reason": "below_min_area_share",
                "area_share": area_share,
                "min_content_area_share": config.min_content_area_share,
                "box": detected_box,
            },
        )
        return None
    return detected_box
