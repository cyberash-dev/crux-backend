from collections.abc import Sequence

from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    FactcheckResponseError,
)
from konspekt.features.factcheck.adapters.outbound.evidence_judge_protocol import (
    evidence_judge_prompt,
    parse_judged_claims,
)
from konspekt.features.factcheck.domain.evidenced_claim import EvidencedClaim
from konspekt.features.factcheck.domain.judged_claim import JudgedClaim
from konspekt.shared.budget import BudgetPort
from konspekt.shared.claude_cli import ClaudeCliRunner

_DEFAULT_MODEL = "claude-opus-5"


class ClaudeCliEvidenceJudge:
    def __init__(
        self,
        budget: BudgetPort,
        model: str = _DEFAULT_MODEL,
        runner: ClaudeCliRunner | None = None,
    ) -> None:
        self._budget = budget
        self._model = model
        self._runner = runner or ClaudeCliRunner()

    def judge_batch(
        self, claims: Sequence[EvidencedClaim], language: str
    ) -> list[JudgedClaim]:
        try:
            return self._request_judgement(claims, language)
        except FactcheckResponseError:
            # per analysis:EXT-011 retry/idempotency: schema-mismatch in the
            # result JSON => one re-request, then the stage fails
            return self._request_judgement(claims, language)

    def _request_judgement(
        self, claims: Sequence[EvidencedClaim], language: str
    ) -> list[JudgedClaim]:
        result = self._runner.run(evidence_judge_prompt(claims, language), self._model)
        self._budget.charge(result.cost_usd)
        return parse_judged_claims(result.text, len(claims))
