from pathlib import Path
from typing import Protocol

from konspekt.worker.domain.video_metadata import VideoMetadata
from konspekt.worker.ports.outbound.running_job import RunningJobPort


class VideoSourcePort(Protocol):
    def metadata(self, youtube_url: str) -> VideoMetadata: ...

    def download(
        self, youtube_url: str, video_id: str, dest_dir: Path
    ) -> RunningJobPort[Path]:
        """The job's outcome is the merged video file; a failed download raises
        DownloadFailedError, a YouTube bot check DownloadBlockedError, from outcome()."""
        ...
