from dataclasses import dataclass

from konspekt.shared.timecode import TimeRange


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    time_range: TimeRange
    text: str
    speaker: str | None


@dataclass(frozen=True, slots=True)
class Transcript:
    language: str
    segments: tuple[TranscriptSegment, ...]

    def full_text(self) -> str:
        return " ".join(segment.text for segment in self.segments)

    def duration_seconds(self) -> float:
        if not self.segments:
            return 0.0
        return self.segments[-1].time_range.end_seconds
