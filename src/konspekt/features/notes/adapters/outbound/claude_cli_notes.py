import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from konspekt.features.notes.adapters.outbound.claude_notes import (
    SECTION_RESPONSE_SCHEMA,
    build_section_prompt,
    parse_section_response,
)
from konspekt.features.notes.application.artifact import NotesArtifactError
from konspekt.features.notes.ports.outbound.notes_llm import (
    IndexedClaim,
    SectionComposition,
)
from konspekt.features.segmentation.domain.segments import SectionPlanEntry
from konspekt.features.visual.domain.frame import Frame
from konspekt.shared.budget import BudgetPort
from konspekt.shared.claude_cli import ClaudeCliRunner


class ClaudeCliNotesComposition:
    def __init__(
        self,
        budget: BudgetPort,
        frames_root: Path,
        model: str = "claude-opus-5",
        runner: ClaudeCliRunner | None = None,
    ) -> None:
        self._budget = budget
        self._frames_root = frames_root
        self._model = model
        self._runner = runner if runner is not None else ClaudeCliRunner()

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
        absolute_frames = [
            replace(frame, image_path=self._absolute(frame.image_path)) for frame in frames
        ]
        prompt = (
            build_section_prompt(
                outline, target, parent, core_text, claims, absolute_frames,
                language, lecture_title, intro_only,
            )
            + "\n\nOpen the frame images listed above with the Read tool to judge "
            "which frames are illustrative before choosing figures.\n"
            "Respond with exactly one JSON object conforming to the JSON Schema below. "
            "No markdown fences, no commentary, nothing before or after the object.\n"
            + json.dumps(SECTION_RESPONSE_SCHEMA)
        )
        allowed_claim_indices = frozenset(
            indexed_claim.global_index for indexed_claim in claims
        )
        try:
            return self._requested_composition(prompt, allowed_claim_indices)
        except NotesArtifactError:
            return self._requested_composition(prompt, allowed_claim_indices)

    def _requested_composition(
        self, prompt: str, allowed_claim_indices: frozenset[int]
    ) -> SectionComposition:
        result = self._runner.run(prompt, self._model, allowed_tools=("Read",))
        self._budget.charge(result.cost_usd)
        return parse_section_response(result.text, allowed_claim_indices)

    def _absolute(self, image_path: Path) -> Path:
        return image_path if image_path.is_absolute() else self._frames_root / image_path
