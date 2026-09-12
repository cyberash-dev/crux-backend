import logging
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace

from konspekt.features.factcheck.application.verdict_gate import apply_outcome_gate
from konspekt.features.factcheck.domain.claims import Verdict, VerificationOutcome
from konspekt.features.factcheck.ports.outbound.factcheck_llm import ClaimVerificationPort
from konspekt.features.factcheck.ports.outbound.verification_fatal_errors import (
    VERIFICATION_FATAL_ERRORS,
)
from konspekt.features.notes.domain.audit import AdditionAction, VerifiedAddition
from konspekt.features.notes.domain.notes import (
    BlockKind,
    BlockOrigin,
    NoteBlock,
    NoteSection,
    Notes,
)

_logger = logging.getLogger(__name__)

_VERIFIED_BLOCK_KINDS = (BlockKind.FACT, BlockKind.DEFINITION)


@dataclass(frozen=True, slots=True)
class _BlockResolution:
    kept_block: NoteBlock | None
    addition: VerifiedAddition


class AdditionVerifier:
    def __init__(
        self,
        verification: ClaimVerificationPort,
        batch_size: int = 5,
        max_workers: int = 4,
    ) -> None:
        self._verification = verification
        self._batch_size = batch_size
        self._max_workers = max_workers

    def verify(self, notes: Notes) -> tuple[Notes, tuple[VerifiedAddition, ...]]:
        section_ids_and_blocks = [
            (section.section_id, block)
            for section in notes.all_sections()
            for block in section.blocks
            if block.kind in _VERIFIED_BLOCK_KINDS
        ]
        if not section_ids_and_blocks:
            return notes, ()
        outcomes = self._verified_outcomes(
            [_claim_text(block) for _, block in section_ids_and_blocks],
            notes.language,
        )
        resolutions = [
            _resolved_block(section_id, block, apply_outcome_gate(outcome))
            for (section_id, block), outcome in zip(
                section_ids_and_blocks, outcomes, strict=True
            )
        ]
        resolution_queue = iter(resolutions)
        verified_notes = replace(
            notes,
            sections=tuple(
                _section_with_resolutions(section, resolution_queue)
                for section in notes.sections
            ),
        )
        return verified_notes, tuple(resolution.addition for resolution in resolutions)

    def _verified_outcomes(
        self, claim_texts: Sequence[str], language: str
    ) -> list[VerificationOutcome]:
        batches = [
            claim_texts[batch_start : batch_start + self._batch_size]
            for batch_start in range(0, len(claim_texts), self._batch_size)
        ]
        with ThreadPoolExecutor(
            max_workers=min(self._max_workers, len(batches))
        ) as pool:
            outcome_batches = list(
                pool.map(
                    lambda batch: self._verify_batch_or_unverified(batch, language),
                    batches,
                )
            )
        return [outcome for outcome_batch in outcome_batches for outcome in outcome_batch]

    def _verify_batch_or_unverified(
        self, batch: Sequence[str], language: str
    ) -> list[VerificationOutcome]:
        try:
            outcomes = self._verification.verify_batch(list(batch), language)
        except VERIFICATION_FATAL_ERRORS:
            raise
        except Exception:
            # per analysis:REQ-028 negative_cases: a port failure yields
            # unverified outcomes and the stage continues
            return _all_unverified(len(batch))
        if len(outcomes) != len(batch):
            return _all_unverified(len(batch))
        return outcomes


def _all_unverified(claim_count: int) -> list[VerificationOutcome]:
    return [
        VerificationOutcome(verdict=Verdict.UNVERIFIED, sources=(), annotation=None)
        for _ in range(claim_count)
    ]


def _claim_text(block: NoteBlock) -> str:
    if block.kind is BlockKind.DEFINITION:
        return f"{block.term} — {block.text}"
    return f"{block.text}"


def _resolved_block(
    section_id: str, block: NoteBlock, gated: VerificationOutcome
) -> _BlockResolution:
    origin = block.origin if block.origin is not None else BlockOrigin.LECTURE
    action = _addition_action(origin, block.kind, gated.verdict)
    if action is AdditionAction.DROPPED:
        _logger.warning(
            "notes.model_added_block_dropped",
            extra={
                "section_id": section_id,
                "kind": block.kind.value,
                "verdict": gated.verdict.value,
            },
        )
        kept_block = None
    elif action is AdditionAction.KEPT_WITH_WARNING:
        kept_block = replace(
            block, text=f"{block.text} ({gated.annotation} — {gated.sources[0]})"
        )
    else:
        kept_block = block
    return _BlockResolution(
        kept_block=kept_block,
        addition=VerifiedAddition(
            text=_claim_text(block),
            origin=origin,
            kind=block.kind,
            verdict=gated.verdict,
            sources=gated.sources,
            annotation=gated.annotation,
            action=action,
        ),
    )


def _addition_action(
    origin: BlockOrigin, kind: BlockKind, verdict: Verdict
) -> AdditionAction:
    if origin is BlockOrigin.MODEL_ADDED:
        if kind is BlockKind.FACT and verdict is not Verdict.CONFIRMED:
            return AdditionAction.DROPPED
        if kind is BlockKind.DEFINITION and verdict is Verdict.DISPUTED:
            return AdditionAction.DROPPED
        return AdditionAction.KEPT
    if verdict is Verdict.DISPUTED:
        return AdditionAction.KEPT_WITH_WARNING
    return AdditionAction.KEPT


def _section_with_resolutions(
    section: NoteSection, resolution_queue: Iterator[_BlockResolution]
) -> NoteSection:
    kept_blocks: list[NoteBlock] = []
    for block in section.blocks:
        if block.kind not in _VERIFIED_BLOCK_KINDS:
            kept_blocks.append(block)
            continue
        resolution = next(resolution_queue)
        if resolution.kept_block is not None:
            kept_blocks.append(resolution.kept_block)
    return replace(
        section,
        blocks=tuple(kept_blocks),
        subsections=tuple(
            _section_with_resolutions(subsection, resolution_queue)
            for subsection in section.subsections
        ),
    )
