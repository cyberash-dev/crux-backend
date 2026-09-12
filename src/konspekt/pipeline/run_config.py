import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_MAX_LLM_USD = 15.0


_CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def lecture_slug(video_file_name: str) -> str:
    stem = Path(video_file_name).stem.lower()
    transliterated = "".join(_CYRILLIC_TO_LATIN.get(char, char) for char in stem)
    collapsed = re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]", "-", transliterated)).strip("-")
    return collapsed or "lecture"


@dataclass(frozen=True, slots=True)
class StageModels:
    segmentation: str = DEFAULT_MODEL
    factcheck: str = DEFAULT_MODEL
    notes: str = DEFAULT_MODEL
    quiz: str = DEFAULT_MODEL


@dataclass(frozen=True, slots=True)
class RunConfig:
    video_path: Path
    out_dir: Path
    language: str = "auto"
    force_from: str | None = None
    max_llm_usd: float = DEFAULT_MAX_LLM_USD
    llm_provider: str = "claude-cli"
    transcriber: str = "elevenlabs"
    commons_candidates: int = 6
    generated_images: bool = False
    models: StageModels = field(default_factory=StageModels)

    @property
    def lecture_dir(self) -> Path:
        return self.out_dir / lecture_slug(self.video_path.name)

    @property
    def work_dir(self) -> Path:
        return self.lecture_dir / "work"
