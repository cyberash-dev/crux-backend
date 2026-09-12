from collections.abc import Mapping
from typing import Any

from konspekt.features.transcription.domain.transcript import Transcript, TranscriptSegment
from konspekt.shared.timecode import TimeRange

_SEGMENT_FIELDS = ("start_seconds", "end_seconds", "text", "speaker")


class TranscriptPayloadError(ValueError):
    pass


def transcript_payload(transcript: Transcript) -> dict[str, object]:
    return {
        "language": transcript.language,
        "segments": [
            {
                "start_seconds": segment.time_range.start_seconds,
                "end_seconds": segment.time_range.end_seconds,
                "text": segment.text,
                "speaker": segment.speaker,
            }
            for segment in transcript.segments
        ],
    }


def parse_transcript_payload(payload: Mapping[str, object]) -> Transcript:
    for field in ("language", "segments"):
        if field not in payload:
            raise TranscriptPayloadError(f"transcript payload is missing field {field!r}")
    raw_segments = payload["segments"]
    if not isinstance(raw_segments, list):
        raise TranscriptPayloadError("segments must be an array")
    segments = tuple(_parse_segment(raw_segment) for raw_segment in raw_segments)
    for previous, current in zip(segments, segments[1:]):
        if current.time_range.start_seconds < previous.time_range.start_seconds:
            raise TranscriptPayloadError("segments must be ordered by start_seconds ascending")
    return Transcript(language=str(payload["language"]), segments=segments)


def _parse_segment(raw_segment: Any) -> TranscriptSegment:
    if not isinstance(raw_segment, Mapping):
        raise TranscriptPayloadError("segment must be an object")
    for field in _SEGMENT_FIELDS:
        if field not in raw_segment:
            raise TranscriptPayloadError(f"segment is missing field {field!r}")
    text = str(raw_segment["text"])
    if not text.strip():
        raise TranscriptPayloadError("segment text must be non-empty after trimming")
    speaker = raw_segment["speaker"]
    if speaker is not None and not isinstance(speaker, str):
        raise TranscriptPayloadError(f"speaker must be string or null, got {speaker!r}")
    try:
        time_range = TimeRange(
            start_seconds=float(raw_segment["start_seconds"]),
            end_seconds=float(raw_segment["end_seconds"]),
        )
    except (TypeError, ValueError) as error:
        raise TranscriptPayloadError(f"invalid segment timing: {error}") from error
    return TranscriptSegment(time_range=time_range, text=text, speaker=speaker)
