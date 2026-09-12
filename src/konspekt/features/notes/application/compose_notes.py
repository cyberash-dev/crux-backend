import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import TypeVar

from konspekt.features.factcheck.domain.claims import CheckedClaim
from konspekt.features.notes.application.artifact import notes_payload, parse_notes_payload
from konspekt.features.notes.application.emphasis import strip_non_prose_emphasis
from konspekt.features.notes.application.resolve_illustrations import IllustrationResolver
from konspekt.features.notes.application.validate_media import (
    MediaViolationKind,
    section_media_violations,
    validate_section_media,
)
from konspekt.features.notes.application.verify_additions import AdditionVerifier
from konspekt.features.notes.domain.audit import VerifiedAddition
from konspekt.features.notes.domain.illustration import IllustrationRequest
from konspekt.features.notes.domain.notes import BlockKind, NoteBlock, NoteSection, Notes
from konspekt.features.notes.ports.outbound.notes_llm import (
    ExternalImagePort,
    IndexedClaim,
    SectionComposition,
    SectionCompositionPort,
)
from konspekt.features.segmentation.application.core_text import core_text_for_range
from konspekt.features.segmentation.domain.segments import (
    SectionPlanEntry,
    SegmentationResult,
)
from konspekt.features.transcription.domain.transcript import Transcript
from konspekt.features.visual.domain.frame import Frame
from konspekt.shared.budget import BudgetExceededError
from konspekt.shared.timecode import TimeRange

_logger = logging.getLogger(__name__)


class NotesValidationError(Exception):
    def __init__(self, errors: Sequence[str]) -> None:
        super().__init__("notes failed media validation: " + "; ".join(errors))
        self.errors = tuple(errors)


class NotesCompositionError(Exception):
    def __init__(self, section_id: str, cause: Exception) -> None:
        super().__init__(
            f"section {section_id!r} failed to compose after one retry: {cause}"
        )
        self.section_id = section_id


@dataclass(frozen=True, slots=True)
class ComposedNotes:
    notes: Notes
    verified_additions: tuple[VerifiedAddition, ...]


@dataclass(frozen=True, slots=True)
class _SectionRequest:
    target: SectionPlanEntry
    parent: SectionPlanEntry | None
    intro_only: bool


class SectionedNotesComposer:
    def __init__(
        self,
        section_port: SectionCompositionPort,
        external_images: ExternalImagePort,
        images_dir: str,
        max_workers: int = 4,
        illustration_resolver: IllustrationResolver | None = None,
        addition_verifier: AdditionVerifier | None = None,
    ) -> None:
        self._section_port = section_port
        self._external_images = external_images
        self._images_dir = images_dir
        self._max_workers = max_workers
        self._illustration_resolver = illustration_resolver
        self._addition_verifier = addition_verifier

    def compose(
        self,
        transcript: Transcript,
        segmentation: SegmentationResult,
        claims: list[CheckedClaim],
        frames: list[Frame],
    ) -> ComposedNotes:
        requests = _section_requests(segmentation.sections_plan)
        indexed_claims = tuple(
            IndexedClaim(global_index, claim) for global_index, claim in enumerate(claims)
        )
        claims_by_target = _grouped_by_target(
            indexed_claims,
            segmentation.sections_plan,
            lambda indexed_claim: _midpoint(indexed_claim.claim.span),
        )
        frames_by_target = _grouped_by_target(
            frames, segmentation.sections_plan, lambda frame: frame.timestamp_seconds
        )
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            compositions = list(
                executor.map(
                    lambda request: self._composed_section(
                        request,
                        transcript,
                        segmentation,
                        claims_by_target.get(request.target.section_id, []),
                        frames_by_target.get(request.target.section_id, []),
                    ),
                    requests,
                )
            )
        composition_by_section_id = {
            request.target.section_id: composition
            for request, composition in zip(requests, compositions)
        }
        blocks_by_section_id = self._blocks_with_illustrations(
            composition_by_section_id, transcript.language
        )
        notes = Notes(
            title=segmentation.lecture_title,
            language=transcript.language,
            sections=tuple(
                _assembled_section(entry, blocks_by_section_id)
                for entry in segmentation.sections_plan
            ),
        )
        notes = self._with_stored_external_figures(notes)
        notes = _without_misplaced_frame_figures(notes, frames)
        notes = strip_non_prose_emphasis(notes)
        verified_additions: tuple[VerifiedAddition, ...] = ()
        if self._addition_verifier is not None:
            notes, verified_additions = self._addition_verifier.verify(notes)
        notes = _without_duplicate_definitions(notes)
        parse_notes_payload(notes_payload(notes), claims_count=len(claims))
        media_errors = [
            error
            for section in notes.all_sections()
            for error in validate_section_media(section, frames)
        ]
        if media_errors:
            raise NotesValidationError(media_errors)
        return ComposedNotes(notes=notes, verified_additions=verified_additions)

    def _blocks_with_illustrations(
        self,
        composition_by_section_id: dict[str, SectionComposition],
        language: str,
    ) -> dict[str, tuple[NoteBlock, ...]]:
        requests_by_section_id = {
            section_id: composition.illustration_request
            for section_id, composition in composition_by_section_id.items()
            if composition.illustration_request is not None
        }
        figure_by_section_id = self._resolved_figures(requests_by_section_id, language)
        return {
            section_id: _with_inserted_figure(
                composition.blocks,
                requests_by_section_id.get(section_id),
                figure_by_section_id.get(section_id),
            )
            for section_id, composition in composition_by_section_id.items()
        }

    def _resolved_figures(
        self, requests_by_section_id: dict[str, IllustrationRequest], language: str
    ) -> Mapping[str, NoteBlock | None]:
        if not requests_by_section_id:
            return {}
        if self._illustration_resolver is None:
            for section_id, request in requests_by_section_id.items():
                _logger.warning(
                    "notes.illustration_request_dropped",
                    extra={
                        "section_id": section_id,
                        "purpose": request.purpose,
                        "reason": "no_resolver_configured",
                    },
                )
            return {}
        return self._illustration_resolver.resolve(requests_by_section_id, language)

    def _composed_section(
        self,
        request: _SectionRequest,
        transcript: Transcript,
        segmentation: SegmentationResult,
        assigned_claims: list[IndexedClaim],
        assigned_frames: list[Frame],
    ) -> SectionComposition:
        try:
            return self._compose_once(
                request, transcript, segmentation, assigned_claims, assigned_frames
            )
        except BudgetExceededError:
            raise
        except Exception:
            try:
                return self._compose_once(
                    request, transcript, segmentation, assigned_claims, assigned_frames
                )
            except BudgetExceededError:
                raise
            except Exception as retry_error:
                raise NotesCompositionError(
                    request.target.section_id, retry_error
                ) from retry_error

    def _compose_once(
        self,
        request: _SectionRequest,
        transcript: Transcript,
        segmentation: SegmentationResult,
        assigned_claims: list[IndexedClaim],
        assigned_frames: list[Frame],
    ) -> SectionComposition:
        return self._section_port.compose_section(
            outline=segmentation.sections_plan,
            target=request.target,
            parent=request.parent,
            core_text=_request_core_text(request, transcript, segmentation),
            claims=assigned_claims,
            frames=assigned_frames,
            language=transcript.language,
            lecture_title=segmentation.lecture_title,
            intro_only=request.intro_only,
        )

    def _with_stored_external_figures(self, notes: Notes) -> Notes:
        return replace(
            notes,
            sections=tuple(self._stored_section(section) for section in notes.sections),
        )

    def _stored_section(self, section: NoteSection) -> NoteSection:
        return replace(
            section,
            blocks=self._stored_blocks(section),
            subsections=tuple(
                self._stored_section(subsection) for subsection in section.subsections
            ),
        )

    def _stored_blocks(self, section: NoteSection) -> tuple[NoteBlock, ...]:
        stored_blocks: list[NoteBlock] = []
        for block in section.blocks:
            if (
                block.kind is BlockKind.FIGURE
                and block.image_path is not None
                and block.image_path.startswith("https://")
            ):
                stored_path = self._external_images.download(
                    block.image_path, self._images_dir
                )
                if stored_path is None:
                    continue
                block = replace(block, image_path=stored_path)
            stored_blocks.append(block)
        return tuple(stored_blocks)


def _with_inserted_figure(
    blocks: tuple[NoteBlock, ...],
    request: IllustrationRequest | None,
    figure: NoteBlock | None,
) -> tuple[NoteBlock, ...]:
    if request is None or figure is None:
        return blocks
    insert_index = min(request.insert_index, len(blocks))
    return blocks[:insert_index] + (figure,) + blocks[insert_index:]


def _section_requests(
    sections_plan: Sequence[SectionPlanEntry],
) -> tuple[_SectionRequest, ...]:
    requests: list[_SectionRequest] = []
    for entry in sections_plan:
        requests.append(
            _SectionRequest(
                target=entry, parent=None, intro_only=bool(entry.subsections)
            )
        )
        requests.extend(
            _SectionRequest(target=subsection, parent=entry, intro_only=False)
            for subsection in entry.subsections
        )
    return tuple(requests)


def _assembled_section(
    entry: SectionPlanEntry,
    blocks_by_section_id: dict[str, tuple[NoteBlock, ...]],
) -> NoteSection:
    return NoteSection(
        section_id=entry.section_id,
        title=entry.title,
        source_spans=(entry.time_range,),
        blocks=blocks_by_section_id[entry.section_id],
        subsections=tuple(
            NoteSection(
                section_id=subsection.section_id,
                title=subsection.title,
                source_spans=(subsection.time_range,),
                blocks=blocks_by_section_id[subsection.section_id],
            )
            for subsection in entry.subsections
        ),
    )


def _request_core_text(
    request: _SectionRequest, transcript: Transcript, segmentation: SegmentationResult
) -> str:
    if not request.intro_only:
        return core_text_for_range(transcript, segmentation, request.target.time_range)
    own_range_texts = [
        core_text_for_range(transcript, segmentation, own_range)
        for own_range in _own_ranges(request.target)
    ]
    return "\n".join(text for text in own_range_texts if text)


def _own_ranges(entry: SectionPlanEntry) -> tuple[TimeRange, ...]:
    ranges: list[TimeRange] = []
    cursor_seconds = entry.time_range.start_seconds
    for subsection in entry.subsections:
        if subsection.time_range.start_seconds > cursor_seconds:
            ranges.append(TimeRange(cursor_seconds, subsection.time_range.start_seconds))
        cursor_seconds = max(cursor_seconds, subsection.time_range.end_seconds)
    if entry.time_range.end_seconds > cursor_seconds:
        ranges.append(TimeRange(cursor_seconds, entry.time_range.end_seconds))
    return tuple(ranges)


_TimedItem = TypeVar("_TimedItem")


def _grouped_by_target(
    items: Iterable[_TimedItem],
    sections_plan: Sequence[SectionPlanEntry],
    point_of: Callable[[_TimedItem], float],
) -> dict[str, list[_TimedItem]]:
    grouped: dict[str, list[_TimedItem]] = {}
    for item in items:
        target_id = _owning_target_id(point_of(item), sections_plan)
        if target_id is not None:
            grouped.setdefault(target_id, []).append(item)
    return grouped


def _owning_target_id(
    point_seconds: float, sections_plan: Sequence[SectionPlanEntry]
) -> str | None:
    for entry in sections_plan:
        if not entry.time_range.contains(point_seconds):
            continue
        for subsection in entry.subsections:
            if subsection.time_range.contains(point_seconds):
                return subsection.section_id
        return entry.section_id
    return None


def _midpoint(time_range: TimeRange) -> float:
    return (time_range.start_seconds + time_range.end_seconds) / 2


def _without_duplicate_definitions(notes: Notes) -> Notes:
    seen_normalized_terms: set[str] = set()
    return replace(
        notes,
        sections=tuple(
            _section_without_duplicate_definitions(section, seen_normalized_terms)
            for section in notes.sections
        ),
    )


def _section_without_duplicate_definitions(
    section: NoteSection, seen_normalized_terms: set[str]
) -> NoteSection:
    kept_blocks: list[NoteBlock] = []
    for block in section.blocks:
        if block.kind is BlockKind.DEFINITION and block.term is not None:
            normalized_term = " ".join(block.term.lower().split())
            if normalized_term in seen_normalized_terms:
                _logger.warning(
                    "notes.duplicate_definition_dropped",
                    extra={"section_id": section.section_id, "term": block.term},
                )
                continue
            seen_normalized_terms.add(normalized_term)
        kept_blocks.append(block)
    return replace(
        section,
        blocks=tuple(kept_blocks),
        subsections=tuple(
            _section_without_duplicate_definitions(subsection, seen_normalized_terms)
            for subsection in section.subsections
        ),
    )


def _without_misplaced_frame_figures(notes: Notes, frames: Sequence[Frame]) -> Notes:
    return replace(
        notes,
        sections=tuple(
            _section_without_misplaced_figures(section, frames)
            for section in notes.sections
        ),
    )


def _section_without_misplaced_figures(
    section: NoteSection, frames: Sequence[Frame]
) -> NoteSection:
    misplaced_blocks = [
        violation.block
        for violation in section_media_violations(section, frames)
        if violation.kind is MediaViolationKind.MISPLACED_FRAME
    ]
    kept_blocks: list[NoteBlock] = []
    for block in section.blocks:
        if block in misplaced_blocks:
            _logger.warning(
                "notes.misplaced_figure_dropped",
                extra={
                    "section_id": section.section_id,
                    "figure_source_ref": block.source_ref,
                },
            )
            continue
        kept_blocks.append(block)
    return replace(
        section,
        blocks=tuple(kept_blocks),
        subsections=tuple(
            _section_without_misplaced_figures(subsection, frames)
            for subsection in section.subsections
        ),
    )
