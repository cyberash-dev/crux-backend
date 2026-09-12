from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    EXTRACTION_SYSTEM_PROMPT,
    FactcheckResponseError,
    parse_extraction_payload,
)
from konspekt.features.factcheck.domain.claims import ExtractedClaim
from konspekt.shared.budget import BudgetPort
from konspekt.shared.claude_cli import ClaudeCliRunner

_DEFAULT_MODEL = "claude-opus-5"

_EXTRACTION_FORMAT_INSTRUCTION = (
    "Respond with exactly one JSON object of the shape "
    '{"claims": [{"claim_text": string, "span_start_seconds": number, '
    '"span_end_seconds": number}]} - no markdown fences, no surrounding prose.'
)


class ClaudeCliClaimExtraction:
    def __init__(
        self,
        budget: BudgetPort,
        model: str = _DEFAULT_MODEL,
        runner: ClaudeCliRunner | None = None,
    ) -> None:
        self._budget = budget
        self._model = model
        self._runner = runner or ClaudeCliRunner()

    def extract_claims(
        self, core_text_with_timestamps: str, language: str
    ) -> list[ExtractedClaim]:
        try:
            return self._request_claims(core_text_with_timestamps, language)
        except FactcheckResponseError:
            # per analysis:EXT-011 retry/idempotency: schema-mismatch in the
            # result JSON => one re-request, then the stage fails
            return self._request_claims(core_text_with_timestamps, language)

    def _request_claims(
        self, core_text_with_timestamps: str, language: str
    ) -> list[ExtractedClaim]:
        prompt = (
            f"{EXTRACTION_SYSTEM_PROMPT}\n"
            f"{_EXTRACTION_FORMAT_INSTRUCTION}\n"
            f"Lecture language: {language}\n"
            "Transcript with timestamps:\n"
            f"{core_text_with_timestamps}"
        )
        result = self._runner.run(prompt, self._model)
        self._budget.charge(result.cost_usd)
        return parse_extraction_payload(result.text)
