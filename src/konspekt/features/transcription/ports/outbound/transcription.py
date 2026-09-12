from pathlib import Path
from typing import Protocol

from konspekt.features.transcription.domain.transcript import Transcript


class TranscriptionPort(Protocol):
    def transcribe(self, audio_path: Path, language_hint: str | None) -> Transcript: ...
