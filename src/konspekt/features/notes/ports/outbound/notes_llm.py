from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from konspekt.features.factcheck.domain.claims import CheckedClaim
from konspekt.features.notes.domain.illustration import (
    CandidateAssessment,
    IllustrationRequest,
)
from konspekt.features.notes.domain.notes import NoteBlock
from konspekt.features.segmentation.domain.segments import SectionPlanEntry
from konspekt.features.visual.domain.frame import Frame


@dataclass(frozen=True, slots=True)
class IndexedClaim:
    global_index: int
    claim: CheckedClaim


@dataclass(frozen=True, slots=True)
class SectionComposition:
    blocks: tuple[NoteBlock, ...]
    illustration_request: IllustrationRequest | None = None


class SectionCompositionPort(Protocol):
    def compose_section(
        self,
        outline: Sequence[SectionPlanEntry],
        target: SectionPlanEntry,
        parent: SectionPlanEntry | None,
        core_text: str,
        claims: Sequence[IndexedClaim],
        frames: Sequence[Frame],
        language: str,
        lecture_title: str,
        intro_only: bool,
    ) -> SectionComposition:
        """Blocks for one outline entry plus at most one illustration request
        (analysis:REQ-027); claim_ref values inside the returned blocks are the
        GLOBAL indices from IndexedClaim. insert_index of the request is a position
        in the returned blocks tuple (0..len(blocks))."""
        ...


class ExternalImagePort(Protocol):
    def download(self, image_url: str, dest_dir: str) -> str | None:
        """Returns the stored path (dest_dir joined with the file name), or None
        when the download failed."""
        ...


@dataclass(frozen=True, slots=True)
class ImageCandidate:
    file_page_url: str
    image_url: str


class ImageSearchPort(Protocol):
    def search(self, query: str, limit: int) -> Sequence[ImageCandidate]:
        """Raster image candidates for a query (analysis:EXT-012); empty on
        provider failure, never raises."""
        ...


class ImageGenerationPort(Protocol):
    def generate(self, prompt: str, dest_dir: str, file_stem: str) -> str | None:
        """Generates one image into dest_dir (analysis:EXT-013); returns the
        stored path, or None when generation failed or is unavailable."""
        ...


class VisionCheckPort(Protocol):
    def assess(self, image_path: str, purpose: str) -> CandidateAssessment:
        """Domain-neutral 0-100 fit score of the image against the stated
        purpose (analysis:DLT-029/DLT-030); the verdict tiers derive from the
        score. Score 0 on any provider failure."""
        ...
