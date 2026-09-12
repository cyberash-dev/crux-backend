import json
import logging

from konspekt.features.notes.domain.illustration import (
    PERFECT_SCORE_THRESHOLD,
    SUITABLE_SCORE_THRESHOLD,
    CandidateAssessment,
)
from konspekt.shared.budget import BudgetExceededError, BudgetPort
from konspekt.shared.claude_cli import ClaudeCliRunner

_logger = logging.getLogger(__name__)

_UNSUITABLE = CandidateAssessment(score=0)


class ClaudeCliVisionCheck:
    def __init__(
        self,
        budget: BudgetPort,
        model: str = "claude-opus-5",
        runner: ClaudeCliRunner | None = None,
    ) -> None:
        self._budget = budget
        self._model = model
        self._runner = runner if runner is not None else ClaudeCliRunner()

    def assess(self, image_path: str, purpose: str) -> CandidateAssessment:
        try:
            result = self._runner.run(
                _vision_prompt(image_path, purpose), self._model, allowed_tools=("Read",)
            )
        except BudgetExceededError:
            raise
        except Exception as error:
            _logger.warning(
                "notes.vision_check_failed",
                extra={"image_path": image_path, "error": repr(error)},
            )
            return _UNSUITABLE
        self._budget.charge(result.cost_usd)
        assessment = _parsed_assessment(result.text)
        if assessment is None:
            _logger.warning(
                "notes.vision_check_malformed",
                extra={"image_path": image_path, "text": result.text[:200]},
            )
            return _UNSUITABLE
        return assessment


def _vision_prompt(image_path: str, purpose: str) -> str:
    return (
        f"Open the image file {image_path} with the Read tool and grade how well it "
        "serves as an illustration in study notes for the following purpose: "
        f"{purpose}\n"
        "Give a fit score from 0 to 100:\n"
        f"- {PERFECT_SCORE_THRESHOLD}-100: the image accurately and clearly depicts "
        "exactly what the purpose describes (subject, view/orientation and any "
        "named parts all match); a student would learn precisely this from the "
        "image alone.\n"
        f"- {SUITABLE_SCORE_THRESHOLD}-{PERFECT_SCORE_THRESHOLD - 1}: the image "
        "accurately depicts the described subject and works as an illustration, "
        "even though details differ from the purpose (other view, missing or "
        "foreign-language labels, extra surrounding context).\n"
        f"- 0-{SUITABLE_SCORE_THRESHOLD - 1}: wrong or unrecognisable subject, "
        "factually inaccurate depiction, low quality, meme-like, decorative or "
        "text-only.\n"
        "Judge factual accuracy of the depiction strictly; when unsure whether "
        f"the depiction is accurate, stay below {PERFECT_SCORE_THRESHOLD}.\n"
        'Answer with exactly one JSON object: {"score": <integer 0-100>, '
        '"reason": "..."}. '
        "No markdown fences, no commentary, nothing before or after the object."
    )


def _parsed_assessment(raw_text: str) -> CandidateAssessment | None:
    try:
        payload = json.loads(_without_fences(raw_text))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    score = payload.get("score")
    if not isinstance(score, int) or isinstance(score, bool):
        return None
    try:
        return CandidateAssessment(score=score)
    except ValueError:
        return None


def _without_fences(raw_text: str) -> str:
    stripped = raw_text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    inner_lines = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
    return "\n".join(inner_lines)
