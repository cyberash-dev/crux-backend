from konspekt.features.notes.domain.illustration import CandidateAssessment


class NoVisionCheck:
    """Grades every candidate unsuitable: web and generated illustrations stay
    off when no vision-capable provider is configured (analysis:INV-022)."""

    def assess(self, image_path: str, purpose: str) -> CandidateAssessment:
        return CandidateAssessment(score=0)
