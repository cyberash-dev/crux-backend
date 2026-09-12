from dataclasses import dataclass

_MAX_DURATION_SECONDS = 4 * 60 * 60
_LIVE_STATUSES = frozenset({"is_live", "is_upcoming", "post_live"})
_PUBLIC_AVAILABILITY = "public"


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    video_id: str
    title: str
    channel: str
    duration_seconds: float | None
    live_status: str | None
    availability: str | None

    def rejection_reason(self) -> str | None:
        if self.live_status in _LIVE_STATUSES:
            return f"live_status is {self.live_status}; only finished recordings are processed"
        if self.availability != _PUBLIC_AVAILABILITY:
            return f"availability is {self.availability}; only public videos are processed"
        if self.duration_seconds is None:
            return "duration is unknown"
        if self.duration_seconds > _MAX_DURATION_SECONDS:
            return f"duration {self.duration_seconds:.0f} s exceeds the 4 h limit"
        return None
