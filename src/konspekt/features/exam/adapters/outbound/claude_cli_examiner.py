import logging
import tempfile
from pathlib import Path

from konspekt.features.exam.adapters.outbound.examiner_output_error import (
    ExaminerOutputError,
)
from konspekt.features.exam.adapters.outbound.examiner_protocol import (
    TURN_SCHEMA,
    examiner_system_prompt,
    examiner_turn_prompt,
    parse_assessment,
)
from konspekt.features.exam.ports.outbound.examiner_assessment import ExaminerAssessment
from konspekt.features.exam.ports.outbound.examiner_model_error import (
    ExaminerModelError,
)
from konspekt.features.exam.ports.outbound.examiner_turn import ExaminerTurn
from konspekt.shared.claude_cli import ClaudeCliError, ClaudeCliResult, ClaudeCliRunner

_DEFAULT_MODEL = "sonnet"
_CALL_TIMEOUT_SECONDS = 50.0
_SYSTEM_PROMPT_FILE_NAME = "examiner-system-prompt.md"

_logger = logging.getLogger(__name__)


class ClaudeCliExaminer:
    def __init__(
        self,
        lecture_notes: str,
        model: str = _DEFAULT_MODEL,
        runner: ClaudeCliRunner | None = None,
    ) -> None:
        self._system_prompt = examiner_system_prompt(lecture_notes)
        self._model = model
        self._runner = runner or ClaudeCliRunner(timeout_seconds=_CALL_TIMEOUT_SECONDS)

    def assess(self, turn: ExaminerTurn) -> ExaminerAssessment:
        prompt = examiner_turn_prompt(turn)
        with tempfile.TemporaryDirectory(prefix="konspekt-exam-") as prompt_dir:
            system_prompt_file = Path(prompt_dir) / _SYSTEM_PROMPT_FILE_NAME
            system_prompt_file.write_text(self._system_prompt, encoding="utf-8")
            first = self._invoke(prompt, system_prompt_file)
            try:
                return parse_assessment(
                    first.structured_output, turn.current, first.cost_usd
                )
            except ExaminerOutputError as error:
                # per service:EXT-003 retry/idempotency: a schema mismatch => one re-request, then the turn fails
                _logger.warning(
                    "exam.structured_output_rerequested", extra={"reason": str(error)}
                )
                second = self._invoke(prompt, system_prompt_file)
                return parse_assessment(
                    second.structured_output,
                    turn.current,
                    first.cost_usd + second.cost_usd,
                )

    def _invoke(self, prompt: str, system_prompt_file: Path) -> ClaudeCliResult:
        try:
            return self._runner.run(
                prompt,
                self._model,
                tools=(),
                system_prompt_file=system_prompt_file,
                json_schema=TURN_SCHEMA,
            )
        except ClaudeCliError as error:
            raise ExaminerModelError(str(error)) from error
