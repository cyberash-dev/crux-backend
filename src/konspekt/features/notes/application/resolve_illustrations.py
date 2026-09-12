import logging
import re
import threading
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor

from konspekt.features.notes.domain.illustration import (
    GENERATED_CAPTION_LABEL_BY_LANGUAGE,
    CandidateAssessment,
    CandidateFit,
    IllustrationConfig,
    IllustrationRequest,
)
from konspekt.features.notes.domain.notes import (
    GENERATED_SOURCE_PREFIX,
    BlockKind,
    FigureProvenance,
    NoteBlock,
)
from konspekt.features.notes.ports.outbound.notes_llm import (
    ExternalImagePort,
    ImageCandidate,
    ImageGenerationPort,
    ImageSearchPort,
    VisionCheckPort,
)
from konspekt.shared.budget import BudgetExceededError

_logger = logging.getLogger(__name__)

GENERATED_SOURCE_REF = GENERATED_SOURCE_PREFIX + "codex"
_FALLBACK_CAPTION_LANGUAGE = "en"
_FILE_STEM_PREFIX = "illustration_"


class _GenerationQuota:
    def __init__(self, maximum: int) -> None:
        self._remaining = maximum
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        with self._lock:
            if self._remaining <= 0:
                return False
            self._remaining -= 1
            return True


class IllustrationResolver:
    def __init__(
        self,
        search: ImageSearchPort,
        downloader: ExternalImagePort,
        generator: ImageGenerationPort,
        vision: VisionCheckPort,
        images_dir: str,
        config: IllustrationConfig = IllustrationConfig(),
    ) -> None:
        self._search = search
        self._downloader = downloader
        self._generator = generator
        self._vision = vision
        self._images_dir = images_dir
        self._config = config

    def resolve(
        self, requests: Mapping[str, IllustrationRequest], language: str
    ) -> Mapping[str, NoteBlock | None]:
        quota = _GenerationQuota(self._config.max_generated_per_lecture)
        section_ids = list(requests)
        with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
            figures = list(
                executor.map(
                    lambda section_id: self._resolved_figure(
                        section_id, requests[section_id], language, quota
                    ),
                    section_ids,
                )
            )
        return dict(zip(section_ids, figures))

    def _resolved_figure(
        self,
        section_id: str,
        request: IllustrationRequest,
        language: str,
        quota: _GenerationQuota,
    ) -> NoteBlock | None:
        try:
            figure, drop_reason = self._commons_or_generated_figure(
                section_id, request, language, quota
            )
        except BudgetExceededError:
            raise
        except Exception as error:
            figure, drop_reason = None, f"error: {error!r}"
        if figure is None:
            _logger.warning(
                "notes.illustration_request_dropped",
                extra={
                    "section_id": section_id,
                    "purpose": request.purpose,
                    "reason": drop_reason,
                },
            )
        return figure

    def _commons_or_generated_figure(
        self,
        section_id: str,
        request: IllustrationRequest,
        language: str,
        quota: _GenerationQuota,
    ) -> tuple[NoteBlock | None, str]:
        perfect_figure, best_suitable = self._graded_commons_figures(request)
        if perfect_figure is not None:
            return perfect_figure, ""
        if self._config.allow_generation:
            generated_figure = self._perfect_generated_figure(
                section_id, request, language, quota
            )
            if generated_figure is not None:
                return generated_figure, ""
        if best_suitable is not None:
            return best_suitable, ""
        return None, "no_candidate_at_least_suitable"

    def _graded_commons_figures(
        self, request: IllustrationRequest
    ) -> tuple[NoteBlock | None, NoteBlock | None]:
        best_suitable: NoteBlock | None = None
        best_score = -1
        for candidate in self._candidates(request.search_query):
            stored_path = self._downloader.download(candidate.image_url, self._images_dir)
            if stored_path is None:
                continue
            assessment = self._assessed(stored_path, request.purpose)
            if assessment.fit is CandidateFit.PERFECT:
                return _commons_figure(stored_path, candidate, request.purpose), None
            if assessment.fit is CandidateFit.SUITABLE and assessment.score > best_score:
                best_suitable = _commons_figure(stored_path, candidate, request.purpose)
                best_score = assessment.score
        return None, best_suitable

    def _perfect_generated_figure(
        self,
        section_id: str,
        request: IllustrationRequest,
        language: str,
        quota: _GenerationQuota,
    ) -> NoteBlock | None:
        if not quota.try_acquire():
            return None
        generated_path = self._generator.generate(
            request.generation_prompt, self._images_dir, _file_stem(section_id)
        )
        if generated_path is None:
            return None
        if self._assessed(generated_path, request.purpose).fit is not CandidateFit.PERFECT:
            return None
        return _generated_figure(generated_path, request.purpose, language)

    def _candidates(self, query: str) -> Sequence[ImageCandidate]:
        try:
            return self._search.search(query, self._config.commons_candidates)
        except BudgetExceededError:
            raise
        except Exception as error:
            _logger.warning(
                "notes.illustration_search_failed",
                extra={"query": query, "error": repr(error)},
            )
            return ()

    def _assessed(self, image_path: str, purpose: str) -> CandidateAssessment:
        try:
            return self._vision.assess(image_path, purpose)
        except BudgetExceededError:
            raise
        except Exception as error:
            _logger.warning(
                "notes.vision_check_failed",
                extra={"image_path": image_path, "error": repr(error)},
            )
            return CandidateAssessment(score=0)


def _commons_figure(stored_path: str, candidate: ImageCandidate, purpose: str) -> NoteBlock:
    return NoteBlock(
        kind=BlockKind.FIGURE,
        image_path=stored_path,
        caption=purpose,
        source_ref=candidate.file_page_url,
        provenance=FigureProvenance.COMMONS,
    )


def _generated_figure(stored_path: str, purpose: str, language: str) -> NoteBlock:
    label = GENERATED_CAPTION_LABEL_BY_LANGUAGE.get(
        language, GENERATED_CAPTION_LABEL_BY_LANGUAGE[_FALLBACK_CAPTION_LANGUAGE]
    )
    return NoteBlock(
        kind=BlockKind.FIGURE,
        image_path=stored_path,
        caption=f"{purpose} ({label})",
        source_ref=GENERATED_SOURCE_REF,
        provenance=FigureProvenance.GENERATED,
    )


def _file_stem(section_id: str) -> str:
    return _FILE_STEM_PREFIX + re.sub(r"[^A-Za-z0-9]+", "_", section_id).strip("_")
