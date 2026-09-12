from collections.abc import Sequence
from pathlib import Path

from PIL import Image

from konspekt.features.visual.application.extract_frames import extract_frames
from konspekt.features.visual.domain.frame import ContentBox, VisualConfig


class PreparedFramesCapture:
    def __init__(self, candidates: list[tuple[float, Path]]) -> None:
        self._candidates = candidates
        self.received_boxes: list[ContentBox | None] = []
        self.probe_requests: list[tuple[Path, tuple[float, ...]]] = []

    def capture_candidates(
        self,
        video_path: Path,
        frames_dir: Path,
        config: VisualConfig,
        content_box: ContentBox | None,
    ) -> list[tuple[float, Path]]:
        self.received_boxes.append(content_box)
        return self._candidates

    def capture_probes(
        self, video_path: Path, probes_dir: Path, timestamps: Sequence[float]
    ) -> list[Path]:
        self.probe_requests.append((probes_dir, tuple(timestamps)))
        probes_dir.mkdir(parents=True, exist_ok=True)
        return [
            a_gradient_image(probes_dir / f"probe_{index:03d}.jpg")
            for index, _ in enumerate(timestamps)
        ]


class FixedLayout:
    def __init__(self, content_box: ContentBox | None) -> None:
        self._content_box = content_box
        self.received_probes: list[tuple[Path, ...]] = []

    def detect_content_box(self, probe_paths: Sequence[Path]) -> ContentBox | None:
        self.received_probes.append(tuple(probe_paths))
        return self._content_box


class FailingLayout:
    def detect_content_box(self, probe_paths: Sequence[Path]) -> ContentBox | None:
        raise RuntimeError("provider exploded")


class DictionaryOcr:
    def __init__(self, texts_by_path: dict[Path, str | None]) -> None:
        self._texts_by_path = texts_by_path
        self.read_paths: list[Path] = []

    def read_text(self, image_path: Path) -> str | None:
        self.read_paths.append(image_path)
        return self._texts_by_path[image_path]


def a_gradient_image(path: Path, is_reversed: bool = False) -> Path:
    image = Image.new("L", (90, 80))
    for x in range(90):
        for y in range(80):
            column = 89 - x if is_reversed else x
            image.putpixel((x, y), column * 255 // 89)
    image.save(path)
    return path


def test_extracts_deduped_ordered_frames_with_ocr(tmp_path: Path) -> None:
    slide_path = a_gradient_image(tmp_path / "slide.jpg")
    duplicate_path = a_gradient_image(tmp_path / "duplicate.jpg")
    other_slide_path = a_gradient_image(tmp_path / "other.jpg", is_reversed=True)
    capture = PreparedFramesCapture(
        [(50.0, other_slide_path), (10.0, slide_path), (30.0, duplicate_path)]
    )
    ocr = DictionaryOcr({slide_path: "first slide", other_slide_path: None})

    extraction = extract_frames(
        tmp_path / "lecture.mp4", tmp_path, VisualConfig(), capture, ocr,
        FixedLayout(None), duration_seconds=100.0,
    )

    assert [frame.timestamp_seconds for frame in extraction.frames] == [10.0, 50.0]
    assert [frame.image_path for frame in extraction.frames] == [slide_path, other_slide_path]
    assert [frame.ocr_text for frame in extraction.frames] == ["first slide", None]


def test_ocr_runs_only_for_dedupe_survivors(tmp_path: Path) -> None:
    slide_path = a_gradient_image(tmp_path / "slide.jpg")
    duplicate_path = a_gradient_image(tmp_path / "duplicate.jpg")
    capture = PreparedFramesCapture([(10.0, slide_path), (30.0, duplicate_path)])
    ocr = DictionaryOcr({slide_path: "first slide"})

    extract_frames(
        tmp_path / "lecture.mp4", tmp_path, VisualConfig(), capture, ocr,
        FixedLayout(None), duration_seconds=100.0,
    )

    assert ocr.read_paths == [slide_path]


def test_valid_content_box_reaches_capture_and_result(tmp_path: Path) -> None:
    """# @covers extraction:REQ-011"""
    slide_path = a_gradient_image(tmp_path / "slide.jpg")
    capture = PreparedFramesCapture([(10.0, slide_path)])
    content_box = ContentBox(x=5, y=5, width=60, height=60)

    extraction = extract_frames(
        tmp_path / "lecture.mp4", tmp_path, VisualConfig(), capture,
        DictionaryOcr({slide_path: None}), FixedLayout(content_box),
        duration_seconds=100.0,
    )

    assert capture.received_boxes == [content_box]
    assert extraction.content_box == content_box


def test_box_below_minimum_area_share_is_dropped_and_frames_still_produced(
    tmp_path: Path,
) -> None:
    """# @covers extraction:REQ-011"""
    slide_path = a_gradient_image(tmp_path / "slide.jpg")
    capture = PreparedFramesCapture([(10.0, slide_path)])
    config = VisualConfig()
    probe_area = 90 * 80
    too_small_side = int((probe_area * config.min_content_area_share) ** 0.5) - 1
    small_box = ContentBox(x=0, y=0, width=too_small_side, height=too_small_side)

    extraction = extract_frames(
        tmp_path / "lecture.mp4", tmp_path, config, capture,
        DictionaryOcr({slide_path: None}), FixedLayout(small_box), duration_seconds=100.0,
    )

    assert capture.received_boxes == [None]
    assert extraction.content_box is None
    assert [frame.image_path for frame in extraction.frames] == [slide_path]


def test_box_exactly_at_minimum_area_share_is_applied(tmp_path: Path) -> None:
    """# @covers extraction:REQ-011"""
    slide_path = a_gradient_image(tmp_path / "slide.jpg")
    capture = PreparedFramesCapture([(10.0, slide_path)])
    config = VisualConfig()
    box_height = int(80 * config.min_content_area_share)
    boundary_box = ContentBox(x=0, y=0, width=90, height=box_height)

    extraction = extract_frames(
        tmp_path / "lecture.mp4", tmp_path, config, capture,
        DictionaryOcr({slide_path: None}), FixedLayout(boundary_box), duration_seconds=100.0,
    )

    assert extraction.content_box == boundary_box


def test_box_outside_frame_is_dropped(tmp_path: Path) -> None:
    """# @covers extraction:REQ-011"""
    slide_path = a_gradient_image(tmp_path / "slide.jpg")
    capture = PreparedFramesCapture([(10.0, slide_path)])
    overflowing_box = ContentBox(x=10, y=0, width=90, height=80)

    extraction = extract_frames(
        tmp_path / "lecture.mp4", tmp_path, VisualConfig(), capture,
        DictionaryOcr({slide_path: None}), FixedLayout(overflowing_box),
        duration_seconds=100.0,
    )

    assert capture.received_boxes == [None]
    assert extraction.content_box is None


def test_layout_port_failure_keeps_run_going_uncropped(tmp_path: Path) -> None:
    """# @covers extraction:REQ-011"""
    slide_path = a_gradient_image(tmp_path / "slide.jpg")
    capture = PreparedFramesCapture([(10.0, slide_path)])

    extraction = extract_frames(
        tmp_path / "lecture.mp4", tmp_path, VisualConfig(), capture,
        DictionaryOcr({slide_path: None}), FailingLayout(), duration_seconds=100.0,
    )

    assert capture.received_boxes == [None]
    assert extraction.content_box is None
    assert [frame.image_path for frame in extraction.frames] == [slide_path]


def test_probes_are_sampled_evenly_between_ten_and_ninety_percent(tmp_path: Path) -> None:
    """# @covers extraction:REQ-011"""
    slide_path = a_gradient_image(tmp_path / "slide.jpg")
    capture = PreparedFramesCapture([(10.0, slide_path)])
    layout = FixedLayout(None)

    extract_frames(
        tmp_path / "lecture.mp4", tmp_path, VisualConfig(probe_count=5), capture,
        DictionaryOcr({slide_path: None}), layout, duration_seconds=100.0,
    )

    assert capture.probe_requests == [(tmp_path / "probes", (10.0, 30.0, 50.0, 70.0, 90.0))]
    assert len(layout.received_probes[0]) == 5


def test_without_probes_layout_is_not_consulted(tmp_path: Path) -> None:
    """# @covers extraction:REQ-011"""
    slide_path = a_gradient_image(tmp_path / "slide.jpg")
    capture = PreparedFramesCapture([(10.0, slide_path)])
    layout = FixedLayout(ContentBox(0, 0, 90, 80))

    extraction = extract_frames(
        tmp_path / "lecture.mp4", tmp_path, VisualConfig(), capture,
        DictionaryOcr({slide_path: None}), layout, duration_seconds=0.0,
    )

    assert layout.received_probes == []
    assert extraction.content_box is None
