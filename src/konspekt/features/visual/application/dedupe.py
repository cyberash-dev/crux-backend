from collections.abc import Sequence

from konspekt.features.visual.application.dhash import hamming_distance
from konspekt.features.visual.domain.frame import VisualConfig


def dedupe_frames(
    candidates: Sequence[tuple[float, str]], config: VisualConfig
) -> list[tuple[float, str]]:
    survivors: list[tuple[float, str]] = []
    for timestamp, dhash in sorted(candidates):
        is_duplicate = any(
            hamming_distance(dhash, kept_dhash) < config.dedupe_hamming_threshold
            for _, kept_dhash in survivors
        )
        if not is_duplicate:
            survivors.append((timestamp, dhash))
    return survivors
