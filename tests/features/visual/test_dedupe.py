from konspekt.features.visual.application.dedupe import dedupe_frames
from konspekt.features.visual.domain.frame import VisualConfig

ZERO_HASH = "0" * 16


def a_hash_at_distance(distance: int) -> str:
    return f"{(1 << distance) - 1:016x}"


def test_pair_below_threshold_collapses_keeping_earliest() -> None:
    """# @covers extraction:INV-010"""
    config = VisualConfig()
    near_hash = a_hash_at_distance(config.dedupe_hamming_threshold - 1)
    candidates = [(30.0, near_hash), (10.0, ZERO_HASH)]

    survivors = dedupe_frames(candidates, config)

    assert survivors == [(10.0, ZERO_HASH)]


def test_pair_exactly_at_threshold_is_kept() -> None:
    """# @covers extraction:INV-010"""
    config = VisualConfig()
    boundary_hash = a_hash_at_distance(config.dedupe_hamming_threshold)
    candidates = [(10.0, ZERO_HASH), (30.0, boundary_hash)]

    survivors = dedupe_frames(candidates, config)

    assert survivors == [(10.0, ZERO_HASH), (30.0, boundary_hash)]


def test_pair_above_threshold_is_kept() -> None:
    """# @covers extraction:INV-010"""
    config = VisualConfig()
    far_hash = a_hash_at_distance(config.dedupe_hamming_threshold + 5)
    candidates = [(10.0, ZERO_HASH), (30.0, far_hash)]

    survivors = dedupe_frames(candidates, config)

    assert survivors == [(10.0, ZERO_HASH), (30.0, far_hash)]


def test_survivors_are_ordered_by_timestamp() -> None:
    """# @covers extraction:INV-010"""
    config = VisualConfig()
    far_hash = a_hash_at_distance(config.dedupe_hamming_threshold + 5)
    candidates = [(30.0, far_hash), (10.0, ZERO_HASH)]

    survivors = dedupe_frames(candidates, config)

    assert survivors == [(10.0, ZERO_HASH), (30.0, far_hash)]
