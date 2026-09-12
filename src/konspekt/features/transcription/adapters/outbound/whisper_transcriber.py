from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from konspekt.features.transcription.domain.transcript import Transcript, TranscriptSegment
from konspekt.shared.timecode import TimeRange


class WhisperNotInstalledError(Exception):
    pass


class WhisperSegmentLike(Protocol):
    start: float
    end: float
    text: str


def transcript_from_whisper_segments(
    segments: Iterable[WhisperSegmentLike], language: str
) -> Transcript:
    mapped_segments = tuple(
        TranscriptSegment(
            time_range=TimeRange(start_seconds=segment.start, end_seconds=segment.end),
            text=segment.text.strip(),
            speaker=None,
        )
        for segment in segments
        if segment.text.strip()
    )
    return Transcript(language=language, segments=mapped_segments)


class WhisperTranscriber:
    def __init__(self, model_size: str = "base") -> None:
        self._model_size = model_size

    def transcribe(self, audio_path: Path, language_hint: str | None) -> Transcript:
        try:
            from faster_whisper import WhisperModel
        except ModuleNotFoundError as error:
            raise WhisperNotInstalledError(
                'faster-whisper is not installed; install konspekt with the "local-whisper" extra'
            ) from error
        model = WhisperModel(self._model_size)
        segments, info = model.transcribe(str(audio_path), language=language_hint, vad_filter=True)
        language = language_hint if language_hint is not None else info.language
        return transcript_from_whisper_segments(segments, language)
