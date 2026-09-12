from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LectureMedia:
    video_path: Path
    audio_path: Path
    duration_seconds: float
