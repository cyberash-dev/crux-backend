from collections.abc import Mapping
from pathlib import Path

from konspekt.features.ingest.domain.media import LectureMedia

_REQUIRED_FIELDS = ("video_path", "audio_path", "duration_seconds")


class MediaPayloadError(ValueError):
    pass


def media_payload(media: LectureMedia) -> dict[str, object]:
    return {
        "video_path": str(media.video_path),
        "audio_path": str(media.audio_path),
        "duration_seconds": media.duration_seconds,
    }


def parse_media_payload(payload: Mapping[str, object]) -> LectureMedia:
    for field in _REQUIRED_FIELDS:
        if field not in payload:
            raise MediaPayloadError(f"media payload is missing field {field!r}")
    duration_seconds = payload["duration_seconds"]
    if not isinstance(duration_seconds, (int, float)) or duration_seconds <= 0:
        raise MediaPayloadError(f"duration_seconds must be > 0, got {duration_seconds!r}")
    return LectureMedia(
        video_path=Path(str(payload["video_path"])),
        audio_path=Path(str(payload["audio_path"])),
        duration_seconds=float(duration_seconds),
    )
