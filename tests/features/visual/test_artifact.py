from pathlib import Path

import pytest

from konspekt.features.visual.application.artifact import (
    frames_payload,
    parse_content_box,
    parse_frames_payload,
)
from konspekt.features.visual.domain.frame import ContentBox, Frame


def test_payload_round_trips() -> None:
    """# @covers extraction:CON-012"""
    frames = [
        Frame(3.5, Path("frames/frame_3500.jpg"), "a1b2c3d4e5f60718", "slide one"),
        Frame(28.0, Path("frames/frame_28000.jpg"), "00ff00ff00ff00ff", None),
    ]

    restored = parse_frames_payload(frames_payload(frames))

    assert restored == frames


def test_payload_orders_frames_by_timestamp() -> None:
    """# @covers extraction:CON-012"""
    frames = [
        Frame(28.0, Path("frames/frame_28000.jpg"), "00ff00ff00ff00ff", None),
        Frame(3.5, Path("frames/frame_3500.jpg"), "a1b2c3d4e5f60718", None),
    ]

    payload = frames_payload(frames)

    timestamps = [entry["timestamp_seconds"] for entry in payload["frames"]]
    assert timestamps == [3.5, 28.0]


@pytest.mark.parametrize(
    "malformed_dhash",
    ["a1b2c3", "a1b2c3d4e5f6071x", "A1B2C3D4E5F60718", "a1b2c3d4e5f607180"],
)
def test_malformed_dhash_is_rejected(malformed_dhash: str) -> None:
    """# @covers extraction:CON-012"""
    payload = {
        "frames": [
            {
                "timestamp_seconds": 3.5,
                "image_path": "frames/frame_3500.jpg",
                "dhash": malformed_dhash,
                "ocr_text": None,
            }
        ]
    }

    with pytest.raises(ValueError, match="dhash"):
        parse_frames_payload(payload)


def test_null_ocr_text_is_accepted() -> None:
    """# @covers extraction:CON-012"""
    payload = {
        "frames": [
            {
                "timestamp_seconds": 3.5,
                "image_path": "frames/frame_3500.jpg",
                "dhash": "a1b2c3d4e5f60718",
                "ocr_text": None,
            }
        ]
    }

    restored = parse_frames_payload(payload)

    assert restored == [Frame(3.5, Path("frames/frame_3500.jpg"), "a1b2c3d4e5f60718", None)]


def test_missing_frame_field_is_rejected() -> None:
    """# @covers extraction:CON-012"""
    payload = {
        "frames": [
            {
                "timestamp_seconds": 3.5,
                "image_path": "frames/frame_3500.jpg",
                "dhash": "a1b2c3d4e5f60718",
            }
        ]
    }

    with pytest.raises(ValueError, match="ocr_text"):
        parse_frames_payload(payload)


def test_payload_carries_content_box() -> None:
    """# @covers extraction:DLT-011"""
    frames = [Frame(3.5, Path("frames/frame_3500.jpg"), "a1b2c3d4e5f60718", None)]

    payload = frames_payload(frames, ContentBox(x=12, y=130, width=1533, height=870))

    assert payload["content_box"] == {"x": 12, "y": 130, "width": 1533, "height": 870}


def test_payload_without_crop_carries_null_content_box() -> None:
    """# @covers extraction:DLT-011"""
    payload = frames_payload([])

    assert payload["content_box"] is None


def test_content_box_round_trips() -> None:
    """# @covers extraction:CON-012"""
    content_box = ContentBox(x=12, y=130, width=1533, height=870)

    restored = parse_content_box(frames_payload([], content_box))

    assert restored == content_box


def test_old_payload_without_content_box_still_parses() -> None:
    """# @covers extraction:DLT-011"""
    payload = {
        "frames": [
            {
                "timestamp_seconds": 3.5,
                "image_path": "frames/frame_3500.jpg",
                "dhash": "a1b2c3d4e5f60718",
                "ocr_text": None,
            }
        ]
    }

    frames = parse_frames_payload(payload)
    content_box = parse_content_box(payload)

    assert frames == [Frame(3.5, Path("frames/frame_3500.jpg"), "a1b2c3d4e5f60718", None)]
    assert content_box is None


def test_null_content_box_parses_as_none() -> None:
    """# @covers extraction:CON-012"""
    assert parse_content_box({"frames": [], "content_box": None}) is None


@pytest.mark.parametrize(
    "malformed_box",
    [
        {"x": 1, "y": 2, "width": 3},
        {"x": "1", "y": 2, "width": 3, "height": 4},
        {"x": -1, "y": 2, "width": 3, "height": 4},
        {"x": 1, "y": 2, "width": 0, "height": 4},
        [1, 2, 3, 4],
    ],
)
def test_malformed_content_box_is_rejected(malformed_box: object) -> None:
    """# @covers extraction:CON-012"""
    with pytest.raises(ValueError, match="content_box"):
        parse_content_box({"frames": [], "content_box": malformed_box})
