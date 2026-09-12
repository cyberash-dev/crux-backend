# @covers extraction:CON-010
from pathlib import Path

import pytest

from konspekt.features.ingest.application.artifact import (
    MediaPayloadError,
    media_payload,
    parse_media_payload,
)
from konspekt.features.ingest.domain.media import LectureMedia


def a_lecture_media(duration_seconds: float = 42.5) -> LectureMedia:
    return LectureMedia(
        video_path=Path("/lectures/lecture.mp4"),
        audio_path=Path("/work/01-audio.flac"),
        duration_seconds=duration_seconds,
    )


def test_payload_round_trips_to_same_media() -> None:
    media = a_lecture_media()

    restored = parse_media_payload(media_payload(media))

    assert restored == media


def test_payload_carries_contract_field_names() -> None:
    media = a_lecture_media()

    payload = media_payload(media)

    assert payload == {
        "video_path": "/lectures/lecture.mp4",
        "audio_path": "/work/01-audio.flac",
        "duration_seconds": 42.5,
    }


@pytest.mark.parametrize("missing_field", ["video_path", "audio_path", "duration_seconds"])
def test_parse_rejects_missing_field(missing_field: str) -> None:
    payload = media_payload(a_lecture_media())
    del payload[missing_field]

    with pytest.raises(MediaPayloadError, match=missing_field):
        parse_media_payload(payload)


@pytest.mark.parametrize("duration_seconds", [0.0, -1.0])
def test_parse_rejects_non_positive_duration(duration_seconds: float) -> None:
    payload = media_payload(a_lecture_media(duration_seconds=duration_seconds))

    with pytest.raises(MediaPayloadError, match="duration_seconds"):
        parse_media_payload(payload)
