import json

from konspekt.features.notes.domain.notes import Notes
from konspekt.features.quiz.adapters.outbound.claude_quiz import (
    QUIZ_RESPONSE_SCHEMA,
    build_quiz_prompt,
    parse_quiz_response,
)
from konspekt.features.quiz.application.artifact import QuizArtifactError
from konspekt.features.quiz.domain.quiz import Quiz, QuizConfig
from konspekt.shared.budget import BudgetPort
from konspekt.shared.claude_cli import ClaudeCliRunner


class ClaudeCliQuizGeneration:
    def __init__(
        self,
        budget: BudgetPort,
        model: str = "claude-opus-5",
        runner: ClaudeCliRunner | None = None,
    ) -> None:
        self._budget = budget
        self._model = model
        self._runner = runner if runner is not None else ClaudeCliRunner()

    def generate(
        self, notes: Notes, config: QuizConfig, coverage_feedback: str | None = None
    ) -> Quiz:
        prompt = (
            build_quiz_prompt(notes, config, coverage_feedback)
            + "\n\nRespond with exactly one JSON object conforming to the JSON Schema "
            "below. No markdown fences, no commentary, nothing before or after the "
            "object.\n" + json.dumps(QUIZ_RESPONSE_SCHEMA)
        )
        try:
            return self._generated_quiz(prompt)
        except QuizArtifactError:
            return self._generated_quiz(prompt)

    def _generated_quiz(self, prompt: str) -> Quiz:
        result = self._runner.run(prompt, self._model)
        self._budget.charge(result.cost_usd)
        return parse_quiz_response(result.text)
