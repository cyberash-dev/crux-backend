import pytest

from konspekt.shared.timecode import TimeRange


def test_duration_is_end_minus_start() -> None:
    time_range = TimeRange(start_seconds=10.0, end_seconds=25.5)

    assert time_range.duration_seconds() == 15.5


def test_rejects_end_before_start() -> None:
    with pytest.raises(ValueError, match="end_seconds must be >= start_seconds"):
        TimeRange(start_seconds=10.0, end_seconds=5.0)


@pytest.mark.parametrize(
    ("moment", "is_inside"),
    [(9.9, False), (10.0, True), (20.0, True), (30.0, False)],
)
def test_contains_moment_within_bounds(moment: float, is_inside: bool) -> None:
    time_range = TimeRange(start_seconds=10.0, end_seconds=20.0)

    assert time_range.contains(moment) is is_inside


@pytest.mark.parametrize(
    ("seconds", "label"),
    [(0.0, "00:00:00"), (75.4, "00:01:15"), (3723.0, "01:02:03")],
)
def test_start_label_formats_as_hh_mm_ss(seconds: float, label: str) -> None:
    time_range = TimeRange(start_seconds=seconds, end_seconds=seconds + 1)

    assert time_range.start_label() == label
