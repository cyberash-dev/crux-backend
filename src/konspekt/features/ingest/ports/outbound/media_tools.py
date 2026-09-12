from pathlib import Path
from typing import Protocol


class MediaToolPort(Protocol):
    def probe_duration(self, video_path: Path) -> float: ...

    def extract_audio(self, video_path: Path, audio_dest: Path) -> Path: ...
