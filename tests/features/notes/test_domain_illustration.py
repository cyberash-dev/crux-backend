# @covers analysis:DLT-030
import pytest

from konspekt.features.notes.domain.illustration import (
    PERFECT_SCORE_THRESHOLD,
    SUITABLE_SCORE_THRESHOLD,
    CandidateAssessment,
    CandidateFit,
)


@pytest.mark.parametrize(
    "score, expected_fit",
    [
        (100, CandidateFit.PERFECT),
        (PERFECT_SCORE_THRESHOLD, CandidateFit.PERFECT),
        (PERFECT_SCORE_THRESHOLD - 1, CandidateFit.SUITABLE),
        (SUITABLE_SCORE_THRESHOLD, CandidateFit.SUITABLE),
        (SUITABLE_SCORE_THRESHOLD - 1, CandidateFit.UNSUITABLE),
        (0, CandidateFit.UNSUITABLE),
    ],
)
def test_fit_is_derived_from_score_thresholds(score: int, expected_fit: CandidateFit) -> None:
    assert CandidateAssessment(score=score).fit is expected_fit


@pytest.mark.parametrize("score", [-1, 101])
def test_score_outside_0_100_is_rejected(score: int) -> None:
    with pytest.raises(ValueError, match="0..100"):
        CandidateAssessment(score=score)
