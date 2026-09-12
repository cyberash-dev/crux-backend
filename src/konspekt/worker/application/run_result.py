from pathlib import Path

from konspekt.pipeline import artifacts_query
from konspekt.worker.domain.video_metadata import VideoMetadata


def run_result(
    out_dir: Path, slug: str, video: VideoMetadata, llm_spend_usd: float | None
) -> dict[str, object]:
    outline = artifacts_query.load_outline(out_dir, slug)
    return {
        "video": {
            "video_id": video.video_id,
            "title": video.title,
            "channel": video.channel,
            "duration_seconds": video.duration_seconds,
        },
        "outline": outline,
        "sections": [
            artifacts_query.load_section(out_dir, slug, section["section_id"])
            for section in outline["sections"]
        ],
        "claims": artifacts_query.load_claims(out_dir, slug, None),
        "quiz": artifacts_query.load_quiz(out_dir, slug),
        "cut_log": artifacts_query.load_cut_log(out_dir, slug),
        "llm_spend_usd": llm_spend_usd,
    }
