from collections.abc import Sequence

import anthropic

from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    FactcheckResponseError,
    charge_usage,
    joined_text,
    reject_refusal,
)
from konspekt.features.factcheck.adapters.outbound.evidence_judge_protocol import (
    evidence_judge_prompt,
    parse_judged_claims,
)
from konspekt.features.factcheck.domain.evidenced_claim import EvidencedClaim
from konspekt.features.factcheck.domain.judged_claim import JudgedClaim
from konspekt.shared.budget import BudgetPort

_DEFAULT_MODEL = "claude-opus-5"
_MAX_TOKENS = 8000


class ClaudeEvidenceJudge:
    def __init__(
        self,
        budget: BudgetPort,
        model: str = _DEFAULT_MODEL,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self._budget = budget
        self._model = model
        self._client = client or anthropic.Anthropic()

    def judge_batch(
        self, claims: Sequence[EvidencedClaim], language: str
    ) -> list[JudgedClaim]:
        try:
            return self._request_judgement(claims, language)
        except FactcheckResponseError:
            # per analysis:EXT-010 error_taxonomy: schema-mismatch in parsed
            # output => one re-request, then the stage fails
            return self._request_judgement(claims, language)

    def _request_judgement(
        self, claims: Sequence[EvidencedClaim], language: str
    ) -> list[JudgedClaim]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": evidence_judge_prompt(claims, language)}],
        )
        charge_usage(self._budget, response)
        reject_refusal(response)
        return parse_judged_claims(joined_text(response), len(claims))
