from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeRange:
    start_seconds: float
    end_seconds: float

    def __post_init__(self) -> None:
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be >= start_seconds")

    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds

    def contains(self, moment_seconds: float) -> bool:
        return self.start_seconds <= moment_seconds <= self.end_seconds

    def start_label(self) -> str:
        return _hh_mm_ss(self.start_seconds)

    def end_label(self) -> str:
        return _hh_mm_ss(self.end_seconds)


def _hh_mm_ss(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 3600:02d}:{whole % 3600 // 60:02d}:{whole % 60:02d}"
