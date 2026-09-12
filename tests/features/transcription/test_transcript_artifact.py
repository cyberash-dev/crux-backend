# @covers extraction:CON-011
import pytest

from konspekt.features.transcription.application.artifact import (
    TranscriptPayloadError,
    parse_transcript_payload,
    transcript_payload,
)
from konspekt.features.transcription.domain.transcript import Transcript, TranscriptSegment
from konspekt.shared.timecode import TimeRange


def a_transcript() -> Transcript:
    return Transcript(
        language="ru",
        segments=(
            TranscriptSegment(
                time_range=TimeRange(start_seconds=0.0, end_seconds=4.2),
                text="Начнём лекцию.",
                speaker="speaker_0",
            ),
            TranscriptSegment(
                time_range=TimeRange(start_seconds=4.2, end_seconds=9.5),
                text="Первый вопрос.",
                speaker=None,
            ),
        ),
    )


def test_payload_round_trips_to_same_transcript() -> None:
    transcript = a_transcript()

    restored = parse_transcript_payload(transcript_payload(transcript))

    assert restored == transcript


def test_payload_carries_contract_field_names() -> None:
    payload = transcript_payload(a_transcript())

    assert payload == {
        "language": "ru",
        "segments": [
            {"start_seconds": 0.0, "end_seconds": 4.2, "text": "Начнём лекцию.", "speaker": "speaker_0"},
            {"start_seconds": 4.2, "end_seconds": 9.5, "text": "Первый вопрос.", "speaker": None},
        ],
    }


def test_parse_rejects_segments_out_of_order() -> None:
    payload = {
        "language": "en",
        "segments": [
            {"start_seconds": 5.0, "end_seconds": 6.0, "text": "later", "speaker": None},
            {"start_seconds": 1.0, "end_seconds": 2.0, "text": "earlier", "speaker": None},
        ],
    }

    with pytest.raises(TranscriptPayloadError, match="ordered by start_seconds"):
        parse_transcript_payload(payload)


def test_millisecond_timestamps_survive_round_trip_within_one_ms() -> None:
    transcript = Transcript(
        language="en",
        segments=(
            TranscriptSegment(
                time_range=TimeRange(start_seconds=1.234, end_seconds=5.678),
                text="millisecond precision",
                speaker=None,
            ),
        ),
    )

    restored = parse_transcript_payload(transcript_payload(transcript))

    assert abs(restored.segments[0].time_range.start_seconds - 1.234) <= 0.001
    assert abs(restored.segments[0].time_range.end_seconds - 5.678) <= 0.001


@pytest.mark.parametrize("missing_field", ["start_seconds", "end_seconds", "text", "speaker"])
def test_parse_rejects_segment_missing_field(missing_field: str) -> None:
    segment = {"start_seconds": 0.0, "end_seconds": 1.0, "text": "hello", "speaker": None}
    del segment[missing_field]
    payload = {"language": "en", "segments": [segment]}

    with pytest.raises(TranscriptPayloadError, match=missing_field):
        parse_transcript_payload(payload)


@pytest.mark.parametrize("missing_field", ["language", "segments"])
def test_parse_rejects_missing_top_level_field(missing_field: str) -> None:
    payload = {
        "language": "en",
        "segments": [{"start_seconds": 0.0, "end_seconds": 1.0, "text": "hello", "speaker": None}],
    }
    del payload[missing_field]

    with pytest.raises(TranscriptPayloadError, match=missing_field):
        parse_transcript_payload(payload)


@pytest.mark.parametrize("blank_text", ["", "   "])
def test_parse_rejects_blank_segment_text(blank_text: str) -> None:
    payload = {
        "language": "en",
        "segments": [{"start_seconds": 0.0, "end_seconds": 1.0, "text": blank_text, "speaker": None}],
    }

    with pytest.raises(TranscriptPayloadError, match="text"):
        parse_transcript_payload(payload)
