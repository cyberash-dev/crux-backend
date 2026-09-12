from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VideoTimeRange:
    start_seconds: float
    end_seconds: float
