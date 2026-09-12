from collections.abc import Sequence

from konspekt.features.factcheck.adapters.outbound.claim_translation_protocol import (
    claim_translation_prompt,
    parse_english_queries,
)
from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    FactcheckResponseError,
)
from konspekt.shared.budget import BudgetPort
from konspekt.shared.claude_cli import ClaudeCliRunner

_DEFAULT_MODEL = "claude-opus-5"


class ClaudeCliClaimTranslation:
    def __init__(
        self,
        budget: BudgetPort,
        model: str = _DEFAULT_MODEL,
        runner: ClaudeCliRunner | None = None,
    ) -> None:
        self._budget = budget
        self._model = model
        self._runner = runner or ClaudeCliRunner()

    def english_queries(self, claim_texts: Sequence[str], language: str) -> list[str]:
        try:
            return self._request_queries(claim_texts, language)
        except FactcheckResponseError:
            # per analysis:EXT-011 retry/idempotency: schema-mismatch in the
            # result JSON => one re-request, then the stage fails
            return self._request_queries(claim_texts, language)

    def _request_queries(self, claim_texts: Sequence[str], language: str) -> list[str]:
        result = self._runner.run(claim_translation_prompt(claim_texts, language), self._model)
        self._budget.charge(result.cost_usd)
        return parse_english_queries(result.text, len(claim_texts))
