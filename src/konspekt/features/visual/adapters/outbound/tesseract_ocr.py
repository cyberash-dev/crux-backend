import subprocess
from pathlib import Path


class TesseractOcr:
    def __init__(self, binary_name: str = "tesseract") -> None:
        self._binary_name = binary_name

    def read_text(self, image_path: Path) -> str | None:
        command = [self._binary_name, str(image_path), "stdout", "-l", "rus+eng"]
        try:
            completed = subprocess.run(command, capture_output=True, text=True)
        except FileNotFoundError:
            return None
        if completed.returncode != 0:
            return None
        return completed.stdout.strip()
