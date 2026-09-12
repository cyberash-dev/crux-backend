# @covers extraction:EXT-003
import importlib.util
from dataclasses import dataclass
from pathlib import Path

import pytest

from konspekt.features.transcription.adapters.outbound.whisper_transcriber import (
    WhisperNotInstalledError,
    WhisperTranscriber,
    transcript_from_whisper_segments,
)


@dataclass(frozen=True)
class WhisperSegmentStandIn:
    start: float
    end: float
    text: str


def test_segments_map_with_null_speaker() -> None:
    segments = (
        WhisperSegmentStandIn(start=0.0, end=2.5, text=" Начнём лекцию."),
        WhisperSegmentStandIn(start=2.5, end=5.0, text=" Первый вопрос."),
    )

    transcript = transcript_from_whisper_segments(segments, language="ru")

    assert [(s.time_range.start_seconds, s.time_range.end_seconds, s.text, s.speaker) for s in transcript.segments] == [
        (0.0, 2.5, "Начнём лекцию.", None),
        (2.5, 5.0, "Первый вопрос.", None),
    ]


def test_detected_language_is_propagated() -> None:
    segments = (WhisperSegmentStandIn(start=0.0, end=1.0, text="Hello"),)

    transcript = transcript_from_whisper_segments(segments, language="en")

    assert transcript.language == "en"


def test_blank_text_segments_are_dropped() -> None:
    segments = (
        WhisperSegmentStandIn(start=0.0, end=1.0, text="   "),
        WhisperSegmentStandIn(start=1.0, end=2.0, text="Hello"),
    )

    transcript = transcript_from_whisper_segments(segments, language="en")

    assert [s.text for s in transcript.segments] == ["Hello"]


@pytest.mark.skipif(
    importlib.util.find_spec("faster_whisper") is not None,
    reason="faster-whisper is installed; the missing-package path is not reachable",
)
def test_missing_package_raises_error_naming_the_extra() -> None:
    transcriber = WhisperTranscriber()

    with pytest.raises(WhisperNotInstalledError, match="local-whisper"):
        transcriber.transcribe(Path("/work/audio.flac"), language_hint=None)
