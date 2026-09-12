from pathlib import Path

from PIL import Image

from konspekt.features.visual.application.dhash import compute_dhash, hamming_distance


def a_horizontal_gradient_image(path: Path, noise_step: int = 0) -> Path:
    image = Image.new("L", (90, 80))
    for x in range(90):
        for y in range(80):
            brightness = x * 255 // 89
            if noise_step and (x + y) % noise_step == 0:
                brightness = min(255, brightness + 2)
            image.putpixel((x, y), brightness)
    image.save(path)
    return path


def a_reversed_gradient_image(path: Path) -> Path:
    image = Image.new("L", (90, 80))
    for x in range(90):
        for y in range(80):
            image.putpixel((x, y), (89 - x) * 255 // 89)
    image.save(path)
    return path


def test_dhash_is_16_hex_chars(tmp_path: Path) -> None:
    image_path = a_horizontal_gradient_image(tmp_path / "plain.png")

    digest = compute_dhash(image_path)

    assert len(digest) == 16
    assert int(digest, 16) >= 0


def test_same_image_has_distance_zero(tmp_path: Path) -> None:
    image_path = a_horizontal_gradient_image(tmp_path / "plain.png")

    first = compute_dhash(image_path)
    second = compute_dhash(image_path)

    assert hamming_distance(first, second) == 0


def test_noisy_copy_stays_below_threshold(tmp_path: Path) -> None:
    plain_path = a_horizontal_gradient_image(tmp_path / "plain.png")
    noisy_path = a_horizontal_gradient_image(tmp_path / "noisy.png", noise_step=7)

    distance = hamming_distance(compute_dhash(plain_path), compute_dhash(noisy_path))

    assert distance < 10


def test_different_patterns_exceed_threshold(tmp_path: Path) -> None:
    gradient_path = a_horizontal_gradient_image(tmp_path / "gradient.png")
    reversed_path = a_reversed_gradient_image(tmp_path / "reversed.png")

    distance = hamming_distance(compute_dhash(gradient_path), compute_dhash(reversed_path))

    assert distance > 10
