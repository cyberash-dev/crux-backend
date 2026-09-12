from pathlib import Path

from PIL import Image

_HASH_WIDTH = 9
_HASH_HEIGHT = 8


def compute_dhash(image_path: Path) -> str:
    with Image.open(image_path) as image:
        grayscale = image.convert("L").resize(
            (_HASH_WIDTH, _HASH_HEIGHT), Image.Resampling.LANCZOS
        )
    pixels = list(grayscale.get_flattened_data())
    bits = 0
    for row in range(_HASH_HEIGHT):
        for col in range(_HASH_WIDTH - 1):
            left = pixels[row * _HASH_WIDTH + col]
            right = pixels[row * _HASH_WIDTH + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def hamming_distance(hex_a: str, hex_b: str) -> int:
    return (int(hex_a, 16) ^ int(hex_b, 16)).bit_count()
