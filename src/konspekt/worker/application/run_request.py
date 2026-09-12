from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RunRequest:
    youtube_url: str
    language: str
    work_dir: Path
    max_llm_usd: float
