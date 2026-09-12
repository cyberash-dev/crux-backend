import pytest

from konspekt.pipeline.run_config import lecture_slug


@pytest.mark.parametrize(
    ("file_name", "slug"),
    [
        ("Lecture 01 - Intro.mp4", "lecture-01-intro"),
        ("simple.mov", "simple"),
        ("UPPER CASE.MP4", "upper-case"),
        ("a -- b.mp4", "a-b"),
    ],
)
def test_lecture_slug_keeps_only_safe_characters(file_name: str, slug: str) -> None:
    assert lecture_slug(file_name) == slug


def test_cyrillic_names_are_transliterated() -> None:
    assert lecture_slug("Квантовая_физика.mkv") == "kvantovaya-fizika"


def test_mixed_cyrillic_name_from_real_lecture() -> None:
    assert lecture_slug("Лекция АН-1.mp4") == "lekciya-an-1"


def test_name_without_any_letters_falls_back_to_lecture() -> None:
    assert lecture_slug("★★★.mp4") == "lecture"
