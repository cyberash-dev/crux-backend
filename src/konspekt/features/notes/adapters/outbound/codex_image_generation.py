import logging
import shutil
import subprocess
from pathlib import Path

_logger = logging.getLogger(__name__)

_OUTPUT_SUFFIXES = (".png", ".jpg", ".jpeg")


class CodexImageGeneration:
    def __init__(self, binary_name: str = "codex", timeout_seconds: float = 420.0) -> None:
        self._binary_name = binary_name
        self._timeout_seconds = timeout_seconds
        self._is_binary_missing_logged = False

    def generate(self, prompt: str, dest_dir: str, file_stem: str) -> str | None:
        if shutil.which(self._binary_name) is None:
            self._log_missing_binary_once()
            return None
        target_name = file_stem + _OUTPUT_SUFFIXES[0]
        command = [
            self._binary_name,
            "exec",
            "--skip-git-repo-check",
            "-s",
            "workspace-write",
            "-C",
            dest_dir,
            _prompt_text(prompt, target_name),
        ]
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            _logger.warning(
                "notes.image_generation_failed",
                extra={"file_stem": file_stem, "error": repr(error)},
            )
            return None
        if completed.returncode != 0:
            _logger.warning(
                "notes.image_generation_failed",
                extra={
                    "file_stem": file_stem,
                    "returncode": completed.returncode,
                    "stderr": completed.stderr.strip()[-500:],
                },
            )
            return None
        produced_path = _produced_file(dest_dir, file_stem)
        if produced_path is None:
            _logger.warning(
                "notes.image_generation_failed",
                extra={"file_stem": file_stem, "reason": "output file missing"},
            )
            return None
        return str(produced_path)

    def _log_missing_binary_once(self) -> None:
        if self._is_binary_missing_logged:
            return
        self._is_binary_missing_logged = True
        _logger.warning(
            "notes.image_generation_unavailable",
            extra={"binary_name": self._binary_name},
        )


def _prompt_text(prompt: str, target_name: str) -> str:
    return (
        "Use your image generation tool to create ONE educational illustration. "
        f"{prompt} Save the resulting image file into the current directory as "
        f"{target_name}. Reply with the file name only."
    )


def _produced_file(dest_dir: str, file_stem: str) -> Path | None:
    for suffix in _OUTPUT_SUFFIXES:
        candidate = Path(dest_dir, file_stem + suffix)
        if candidate.is_file():
            return candidate
    return None
