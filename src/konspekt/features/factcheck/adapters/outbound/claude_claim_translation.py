from collections.abc import Sequence

import anthropic

from konspekt.features.factcheck.adapters.outbound.claim_translation_protocol import (
    claim_translation_prompt,
    parse_english_queries,
)
from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    FactcheckResponseError,
    charge_usage,
    joined_text,
    reject_refusal,
)
from konspekt.shared.budget import BudgetPort

_DEFAULT_MODEL = "claude-opus-5"
_MAX_TOKENS = 8000


class ClaudeClaimTranslation:
    def __init__(
        self,
        budget: BudgetPort,
        model: str = _DEFAULT_MODEL,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self._budget = budget
        self._model = model
        self._client = client or anthropic.Anthropic()

    def english_queries(self, claim_texts: Sequence[str], language: str) -> list[str]:
        try:
            return self._request_queries(claim_texts, language)
        except FactcheckResponseError:
            # per analysis:EXT-010 error_taxonomy: schema-mismatch in parsed
            # output => one re-request, then the stage fails
            return self._request_queries(claim_texts, language)

    def _request_queries(self, claim_texts: Sequence[str], language: str) -> list[str]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            messages=[
                {"role": "user", "content": claim_translation_prompt(claim_texts, language)}
            ],
        )
        charge_usage(self._budget, response)
        reject_refusal(response)
        return parse_english_queries(joined_text(response), len(claim_texts))
