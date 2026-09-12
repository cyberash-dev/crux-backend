from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal, Protocol

import httpx
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError

from konspekt.features.transcription.domain.transcript import Transcript, TranscriptSegment
from konspekt.shared.timecode import TimeRange

ScribeModelId = Literal["scribe_v2", "scribe_v1"]

PAUSE_SPLIT_SECONDS = 1.2
MAX_SEGMENT_SECONDS = 30.0
MICRO_PAUSE_SECONDS = 0.2

_PRIMARY_SUBTAG_BY_ISO639_3 = {"eng": "en", "rus": "ru"}


def normalize_language_code(provider_code: str) -> str:
    return _PRIMARY_SUBTAG_BY_ISO639_3.get(provider_code, provider_code)


class TranscriptionConfigurationError(Exception):
    pass


class TranscriptionProviderError(Exception):
    pass


class ScribeWord(Protocol):
    text: str
    start: float | None
    end: float | None
    speaker_id: str | None


class ScribeResponse(Protocol):
    language_code: str
    words: Sequence[ScribeWord]


def segments_from_scribe_words(words: Iterable[ScribeWord]) -> tuple[TranscriptSegment, ...]:
    segments: list[TranscriptSegment] = []
    turn_words: list[ScribeWord] = []
    for word in words:
        if not word.text.strip():
            continue
        if turn_words and _is_segment_boundary(turn_words, word):
            segments.append(_segment_from_turn(turn_words))
            turn_words = []
        turn_words.append(word)
    if turn_words:
        segments.append(_segment_from_turn(turn_words))
    return tuple(segments)


def _is_segment_boundary(turn_words: list[ScribeWord], word: ScribeWord) -> bool:
    previous_word = turn_words[-1]
    if word.speaker_id != previous_word.speaker_id:
        return True
    turn_start = turn_words[0].start
    if word.start is None or previous_word.end is None or turn_start is None:
        return False
    pause_seconds = word.start - previous_word.end
    if pause_seconds > PAUSE_SPLIT_SECONDS:
        return True
    turn_duration_seconds = previous_word.end - turn_start
    return turn_duration_seconds >= MAX_SEGMENT_SECONDS and pause_seconds > MICRO_PAUSE_SECONDS


def _segment_from_turn(turn_words: list[ScribeWord]) -> TranscriptSegment:
    first_word = turn_words[0]
    last_word = turn_words[-1]
    if first_word.start is None or last_word.end is None:
        raise TranscriptionProviderError("Scribe word is missing start/end timestamps")
    return TranscriptSegment(
        time_range=TimeRange(start_seconds=first_word.start, end_seconds=last_word.end),
        text=" ".join(word.text.strip() for word in turn_words),
        speaker=first_word.speaker_id,
    )


class ElevenLabsTranscriber:
    def __init__(self, client: ElevenLabs, model_id: ScribeModelId = "scribe_v2") -> None:
        self._client = client
        self._model_id: ScribeModelId = model_id

    def transcribe(self, audio_path: Path, language_hint: str | None) -> Transcript:
        response = self._convert_with_retry(audio_path, language_hint)
        language = (
            language_hint
            if language_hint is not None
            else normalize_language_code(response.language_code)
        )
        return Transcript(language=language, segments=segments_from_scribe_words(response.words))

    def _convert_with_retry(self, audio_path: Path, language_hint: str | None) -> ScribeResponse:
        try:
            return self._convert(audio_path, language_hint)
        except ApiError as error:
            if error.status_code == 401:
                raise TranscriptionConfigurationError(
                    "ElevenLabs rejected the request with HTTP 401; check ELEVENLABS_API_KEY"
                ) from error
            if error.status_code is None or error.status_code < 500:
                raise
            return self._convert_retry(audio_path, language_hint)
        except (httpx.TransportError, OSError):
            return self._convert_retry(audio_path, language_hint)

    def _convert_retry(self, audio_path: Path, language_hint: str | None) -> ScribeResponse:
        try:
            return self._convert(audio_path, language_hint)
        except ApiError as retry_error:
            raise TranscriptionProviderError(
                f"ElevenLabs speech-to-text failed after retry: HTTP {retry_error.status_code}"
            ) from retry_error
        except (httpx.TransportError, OSError) as retry_error:
            raise TranscriptionProviderError(
                f"ElevenLabs speech-to-text failed after retry: {retry_error}"
            ) from retry_error

    def _convert(self, audio_path: Path, language_hint: str | None) -> ScribeResponse:
        with audio_path.open("rb") as audio_file:
            if language_hint is None:
                return self._client.speech_to_text.convert(
                    model_id=self._model_id, file=audio_file, diarize=True
                )
            return self._client.speech_to_text.convert(
                model_id=self._model_id, file=audio_file, diarize=True, language_code=language_hint
            )
