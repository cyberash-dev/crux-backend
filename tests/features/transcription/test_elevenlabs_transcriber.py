# @covers extraction:EXT-001
# @covers extraction:REQ-010
# @covers extraction:CON-011
# @covers extraction:DLT-010
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import httpx
import pytest
from elevenlabs.core.api_error import ApiError

from konspekt.features.transcription.adapters.outbound.elevenlabs_transcriber import (
    ElevenLabsTranscriber,
    TranscriptionConfigurationError,
    TranscriptionProviderError,
    segments_from_scribe_words,
)


@dataclass(frozen=True)
class ScribeWordStandIn:
    text: str
    start: float | None
    end: float | None
    speaker_id: str | None


@dataclass(frozen=True)
class ScribeResponseStandIn:
    language_code: str
    words: tuple[ScribeWordStandIn, ...]


@dataclass
class SpeechToTextStub:
    outcomes: list[Any]
    convert_calls: list[dict[str, Any]] = field(default_factory=list)

    def convert(self, **kwargs: Any) -> Any:
        self.convert_calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@dataclass
class ScribeClientStub:
    speech_to_text: SpeechToTextStub


def a_scribe_client(*outcomes: Any) -> ScribeClientStub:
    return ScribeClientStub(speech_to_text=SpeechToTextStub(outcomes=list(outcomes)))


def transcribe_via_stub(client: ScribeClientStub, language_hint: str | None) -> Any:
    with NamedTemporaryFile(suffix=".flac") as audio_file:
        return ElevenLabsTranscriber(client=client).transcribe(  # type: ignore[arg-type]
            Path(audio_file.name), language_hint
        )


RU_WORDS = (
    ScribeWordStandIn(text="Начнём", start=0.0, end=0.5, speaker_id="speaker_0"),
    ScribeWordStandIn(text="лекцию", start=0.6, end=1.2, speaker_id="speaker_0"),
    ScribeWordStandIn(text="Есть", start=2.0, end=2.3, speaker_id="speaker_1"),
    ScribeWordStandIn(text="вопрос", start=2.4, end=2.9, speaker_id="speaker_1"),
    ScribeWordStandIn(text="Продолжим", start=3.5, end=4.1, speaker_id="speaker_0"),
)

EN_WORDS = (
    ScribeWordStandIn(text="Welcome", start=0.0, end=0.4, speaker_id="speaker_0"),
    ScribeWordStandIn(text="everyone", start=0.5, end=1.0, speaker_id="speaker_0"),
    ScribeWordStandIn(text="Thanks", start=1.5, end=1.9, speaker_id="speaker_1"),
)


def test_ru_words_group_into_speaker_turn_segments() -> None:
    segments = segments_from_scribe_words(RU_WORDS)

    assert [(segment.speaker, segment.text) for segment in segments] == [
        ("speaker_0", "Начнём лекцию"),
        ("speaker_1", "Есть вопрос"),
        ("speaker_0", "Продолжим"),
    ]
    assert segments[0].time_range.start_seconds == 0.0
    assert segments[0].time_range.end_seconds == 1.2
    assert segments[2].time_range.start_seconds == 3.5


def test_en_words_group_into_speaker_turn_segments() -> None:
    segments = segments_from_scribe_words(EN_WORDS)

    assert [(segment.speaker, segment.text) for segment in segments] == [
        ("speaker_0", "Welcome everyone"),
        ("speaker_1", "Thanks"),
    ]


def test_single_speaker_without_labels_yields_one_segment_with_null_speaker() -> None:
    words = (
        ScribeWordStandIn(text="Solo", start=0.0, end=0.4, speaker_id=None),
        ScribeWordStandIn(text="lecture", start=0.5, end=1.0, speaker_id=None),
    )

    segments = segments_from_scribe_words(words)

    assert [(segment.speaker, segment.text) for segment in segments] == [(None, "Solo lecture")]


def test_long_pause_starts_new_segment_for_same_speaker() -> None:
    words = (
        ScribeWordStandIn(text="Итак", start=0.0, end=1.0, speaker_id="speaker_0"),
        ScribeWordStandIn(text="далее", start=3.0, end=4.0, speaker_id="speaker_0"),
    )

    segments = segments_from_scribe_words(words)

    assert [(segment.time_range.start_seconds, segment.time_range.end_seconds, segment.text) for segment in segments] == [
        (0.0, 1.0, "Итак"),
        (3.0, 4.0, "далее"),
    ]


def test_long_monologue_splits_at_micro_pause_after_max_duration() -> None:
    words = tuple(
        ScribeWordStandIn(text=f"слово{index}", start=index * 2.0, end=index * 2.0 + 1.7, speaker_id="speaker_0")
        for index in range(35)
    )

    segments = segments_from_scribe_words(words)

    assert [(segment.time_range.start_seconds, segment.time_range.end_seconds) for segment in segments] == [
        (0.0, 31.7),
        (32.0, 63.7),
        (64.0, 69.7),
    ]
    assert all(segment.speaker == "speaker_0" for segment in segments)


def test_blank_text_words_are_dropped() -> None:
    words = (
        ScribeWordStandIn(text="Hello", start=0.0, end=0.4, speaker_id="speaker_0"),
        ScribeWordStandIn(text=" ", start=0.4, end=0.5, speaker_id="speaker_0"),
        ScribeWordStandIn(text="there", start=0.5, end=1.0, speaker_id="speaker_0"),
    )

    segments = segments_from_scribe_words(words)

    assert [segment.text for segment in segments] == ["Hello there"]


def test_auto_language_takes_provider_detection() -> None:
    client = a_scribe_client(ScribeResponseStandIn(language_code="ru", words=RU_WORDS))

    transcript = transcribe_via_stub(client, language_hint=None)

    assert transcript.language == "ru"
    assert "language_code" not in client.speech_to_text.convert_calls[0]


def test_language_hint_reaches_provider_and_artifact() -> None:
    client = a_scribe_client(ScribeResponseStandIn(language_code="eng", words=EN_WORDS))

    transcript = transcribe_via_stub(client, language_hint="en")

    assert transcript.language == "en"
    assert client.speech_to_text.convert_calls[0]["language_code"] == "en"


def test_language_outside_ru_en_is_recorded_verbatim() -> None:
    client = a_scribe_client(ScribeResponseStandIn(language_code="deu", words=EN_WORDS))

    transcript = transcribe_via_stub(client, language_hint=None)

    assert transcript.language == "deu"


def test_convert_receives_scribe_model_and_diarization() -> None:
    client = a_scribe_client(ScribeResponseStandIn(language_code="en", words=EN_WORDS))

    transcribe_via_stub(client, language_hint=None)

    convert_call = client.speech_to_text.convert_calls[0]
    assert convert_call["model_id"] == "scribe_v2"
    assert convert_call["diarize"] is True


def test_unauthorized_key_raises_configuration_error() -> None:
    client = a_scribe_client(ApiError(status_code=401, body="unauthorized"))

    with pytest.raises(TranscriptionConfigurationError, match="ELEVENLABS_API_KEY"):
        transcribe_via_stub(client, language_hint=None)


def test_server_error_is_retried_once_then_succeeds() -> None:
    client = a_scribe_client(
        ApiError(status_code=503, body="unavailable"),
        ScribeResponseStandIn(language_code="en", words=EN_WORDS),
    )

    transcript = transcribe_via_stub(client, language_hint=None)

    assert transcript.language == "en"
    assert len(client.speech_to_text.convert_calls) == 2


def test_transport_error_is_retried_once_then_succeeds() -> None:
    client = a_scribe_client(
        httpx.ConnectError("Connection reset by peer"),
        ScribeResponseStandIn(language_code="en", words=EN_WORDS),
    )

    transcript = transcribe_via_stub(client, language_hint=None)

    assert transcript.language == "en"
    assert len(client.speech_to_text.convert_calls) == 2


def test_transport_error_twice_raises_provider_error() -> None:
    client = a_scribe_client(
        ConnectionResetError(54, "Connection reset by peer"),
        httpx.ReadError("connection closed mid-response"),
    )

    with pytest.raises(TranscriptionProviderError, match="connection closed mid-response"):
        transcribe_via_stub(client, language_hint=None)

    assert len(client.speech_to_text.convert_calls) == 2


def test_server_error_twice_raises_provider_error() -> None:
    client = a_scribe_client(
        ApiError(status_code=503, body="unavailable"),
        ApiError(status_code=502, body="bad gateway"),
    )

    with pytest.raises(TranscriptionProviderError, match="502"):
        transcribe_via_stub(client, language_hint=None)

    assert len(client.speech_to_text.convert_calls) == 2


# @covers extraction:CON-011
@pytest.mark.parametrize(
    ("provider_code", "stored_language"),
    [("eng", "en"), ("rus", "ru"), ("deu", "deu")],
)
def test_auto_detected_iso639_3_code_is_normalized_to_primary_subtag(
    provider_code: str, stored_language: str
) -> None:
    client = a_scribe_client(ScribeResponseStandIn(language_code=provider_code, words=EN_WORDS))

    transcript = transcribe_via_stub(client, language_hint=None)

    assert transcript.language == stored_language
