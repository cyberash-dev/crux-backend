from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Frame:
    timestamp_seconds: float
    image_path: Path
    dhash: str
    ocr_text: str | None


@dataclass(frozen=True, slots=True)
class ContentBox:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("content box needs non-negative origin and positive size")

    def fits_inside(self, frame_width: int, frame_height: int) -> bool:
        return self.x + self.width <= frame_width and self.y + self.height <= frame_height

    def area_share(self, frame_width: int, frame_height: int) -> float:
        return (self.width * self.height) / (frame_width * frame_height)


@dataclass(frozen=True, slots=True)
class VisualConfig:
    sampling_interval_seconds: float = 25.0
    scene_threshold: float = 0.20
    dedupe_hamming_threshold: int = 10
    probe_count: int = 5
    min_content_area_share: float = 0.4


@dataclass(frozen=True, slots=True)
class FrameExtraction:
    frames: tuple[Frame, ...]
    content_box: ContentBox | None
