import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from konspekt.features.visual.domain.frame import ContentBox, Frame

_DHASH_PATTERN = re.compile(r"^[0-9a-f]{16}$")
_FRAME_FIELDS = ("timestamp_seconds", "image_path", "dhash", "ocr_text")
_CONTENT_BOX_FIELDS = ("x", "y", "width", "height")


def frames_payload(
    frames: Sequence[Frame], content_box: ContentBox | None = None
) -> dict[str, Any]:
    ordered = sorted(frames, key=lambda frame: frame.timestamp_seconds)
    return {
        "frames": [
            {
                "timestamp_seconds": frame.timestamp_seconds,
                "image_path": str(frame.image_path),
                "dhash": frame.dhash,
                "ocr_text": frame.ocr_text,
            }
            for frame in ordered
        ],
        "content_box": None
        if content_box is None
        else {
            "x": content_box.x,
            "y": content_box.y,
            "width": content_box.width,
            "height": content_box.height,
        },
    }


def parse_content_box(payload: Mapping[str, Any]) -> ContentBox | None:
    raw_box = payload.get("content_box")
    if raw_box is None:
        return None
    if not isinstance(raw_box, Mapping):
        raise ValueError("content_box is not an object")
    for field in _CONTENT_BOX_FIELDS:
        if field not in raw_box:
            raise ValueError(f"content_box is missing field {field!r}")
        if not isinstance(raw_box[field], int) or isinstance(raw_box[field], bool):
            raise ValueError(f"content_box field {field!r} is not an integer")
    try:
        return ContentBox(
            x=raw_box["x"], y=raw_box["y"], width=raw_box["width"], height=raw_box["height"]
        )
    except ValueError as error:
        raise ValueError(f"content_box is invalid: {error}") from error


def parse_frames_payload(payload: Mapping[str, Any]) -> list[Frame]:
    if "frames" not in payload:
        raise ValueError("frames payload is missing field 'frames'")
    frames: list[Frame] = []
    for entry in payload["frames"]:
        for field in _FRAME_FIELDS:
            if field not in entry:
                raise ValueError(f"frame entry is missing field {field!r}")
        dhash = entry["dhash"]
        if not isinstance(dhash, str) or not _DHASH_PATTERN.match(dhash):
            raise ValueError(f"dhash {dhash!r} is not 16 lowercase hex chars")
        frames.append(
            Frame(
                timestamp_seconds=entry["timestamp_seconds"],
                image_path=Path(entry["image_path"]),
                dhash=dhash,
                ocr_text=entry["ocr_text"],
            )
        )
    return frames
