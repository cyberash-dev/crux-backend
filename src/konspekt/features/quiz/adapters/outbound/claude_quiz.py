import json

from anthropic import Anthropic

from konspekt.features.notes.domain.notes import BlockKind, NoteSection, Notes
from konspekt.features.quiz.application.artifact import QuizArtifactError, parse_quiz_payload
from konspekt.features.quiz.domain.quiz import CHOICE_OPTION_COUNT, Quiz, QuizConfig
from konspekt.shared.budget import BudgetPort

QUIZ_MAX_TOKENS = 16_000
CHOICE_SHARE = 0.7
RUBRIC_MIN_POINTS = 3
RUBRIC_MAX_POINTS = 6
RUBRIC_MIN_CONCEPTS = 2
RUBRIC_MAX_CONCEPTS = 4

_INPUT_USD_PER_TOKEN = 5 / 1_000_000
_OUTPUT_USD_PER_TOKEN = 25 / 1_000_000

_RUBRIC_SCHEMA: dict[str, object] = {
    "type": ["object", "null"],
    "properties": {
        "max_points": {
            "type": "integer",
            "minimum": RUBRIC_MIN_POINTS,
            "maximum": RUBRIC_MAX_POINTS,
        },
        "concepts": {
            "type": "array",
            "minItems": RUBRIC_MIN_CONCEPTS,
            "maxItems": RUBRIC_MAX_CONCEPTS,
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "points": {"type": "integer", "minimum": 1},
                },
                "required": ["description", "points"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["max_points", "concepts"],
    "additionalProperties": False,
}

_QUESTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "question_id": {"type": "string"},
        "type": {"type": "string", "enum": ["single_choice", "multi_select", "open"]},
        "prompt": {"type": "string"},
        "options": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "minItems": CHOICE_OPTION_COUNT,
            "maxItems": CHOICE_OPTION_COUNT,
        },
        "correct_options": {
            "type": ["array", "null"],
            "items": {"type": "integer"},
            "minItems": 1,
        },
        "model_answer": {"type": ["string", "null"]},
        "rubric": _RUBRIC_SCHEMA,
        "section_id": {"type": "string"},
    },
    "required": [
        "question_id",
        "type",
        "prompt",
        "options",
        "correct_options",
        "model_answer",
        "rubric",
        "section_id",
    ],
    "additionalProperties": False,
}

QUIZ_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": _QUESTION_SCHEMA}},
    "required": ["questions"],
    "additionalProperties": False,
}


class QuizGenerationRefusedError(Exception):
    pass


def build_quiz_prompt(
    notes: Notes, config: QuizConfig, coverage_feedback: str | None = None
) -> str:
    target_count = config.target_for(len(notes.sections))
    choice_count = round(target_count * CHOICE_SHARE)
    open_count = target_count - choice_count
    section_parts = [_section_text(section) for section in notes.sections]
    return (
        f"Create a self-check quiz for the lecture notes titled {notes.title!r}.\n"
        f"Write every question and answer in the language of the notes "
        f"(language code: {notes.language}).\n"
        f"Generate exactly {target_count} questions: {choice_count} choice questions "
        "(mix the types 'single_choice' and 'multi_select', at least one of each) "
        f"and {open_count} of type 'open'.\n"
        "Rules:\n"
        f"- single_choice questions carry exactly {CHOICE_OPTION_COUNT} options and "
        "correct_options with exactly ONE 0-based index; model_answer and rubric "
        "are null.\n"
        f"- multi_select questions carry exactly {CHOICE_OPTION_COUNT} options and "
        "correct_options with TWO OR MORE unique 0-based indices; model_answer and "
        "rubric are null.\n"
        "- open questions carry a model_answer (the reference answer) and a grading "
        "rubric; options and correct_options are null. The rubric has max_points "
        f"between {RUBRIC_MIN_POINTS} and {RUBRIC_MAX_POINTS} and "
        f"{RUBRIC_MIN_CONCEPTS}-{RUBRIC_MAX_CONCEPTS} required concepts, each with a "
        "short description in the language of the notes and integer points >= 1; "
        "concept points sum to exactly max_points.\n"
        "- section_id of every question is one of the section ids listed below.\n"
        f"- Cover ALL TOP-LEVEL sections: every top-level section gets at least "
        f"{config.questions_per_section} questions; questions may target subsections "
        "and then count toward the parent section. Ask about the material, not "
        "about the notes formatting. Cover transition and summary sections too: "
        "at least one question about the section's key idea.\n"
        + _rejection_paragraph(coverage_feedback)
        + "\n## Note sections\n"
        + "\n".join(section_parts)
    )


def _rejection_paragraph(coverage_feedback: str | None) -> str:
    if coverage_feedback is None:
        return ""
    return (
        f"\nPREVIOUS ATTEMPT REJECTED: {coverage_feedback}\n"
        "Every section listed below MUST receive questions — even a short or "
        "transitional section: ask about its key idea.\n"
    )


def parse_quiz_response(raw_text: str) -> Quiz:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise QuizArtifactError(f"quiz response is not valid JSON: {error}") from error
    return parse_quiz_payload(payload)


class ClaudeQuizGeneration:
    def __init__(
        self,
        budget: BudgetPort,
        client: Anthropic | None = None,
        model: str = "claude-opus-5",
    ) -> None:
        self._budget = budget
        self._client = client if client is not None else Anthropic()
        self._model = model

    def generate(
        self, notes: Notes, config: QuizConfig, coverage_feedback: str | None = None
    ) -> Quiz:
        prompt = build_quiz_prompt(notes, config, coverage_feedback)
        try:
            return self._generated_quiz(prompt)
        except QuizArtifactError:
            return self._generated_quiz(prompt)

    def _generated_quiz(self, prompt: str) -> Quiz:
        with self._client.messages.stream(
            model=self._model,
            max_tokens=QUIZ_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": QUIZ_RESPONSE_SCHEMA}},
        ) as stream:
            message = stream.get_final_message()
        self._budget.charge(
            message.usage.input_tokens * _INPUT_USD_PER_TOKEN
            + message.usage.output_tokens * _OUTPUT_USD_PER_TOKEN
        )
        if message.stop_reason == "refusal":
            raise QuizGenerationRefusedError(
                "quiz generation request was refused by the model"
            )
        raw_text = next(block.text for block in message.content if block.type == "text")
        return parse_quiz_response(raw_text)


def _section_text(section: NoteSection) -> str:
    parts = [f"### {section.section_id}: {section.title}\n{_blocks_text(section)}"]
    parts.extend(
        f"#### {subsection.section_id} (subsection of {section.section_id}): "
        f"{subsection.title}\n{_blocks_text(subsection)}"
        for subsection in section.subsections
    )
    return "\n".join(parts)


def _blocks_text(section: NoteSection) -> str:
    return " ".join(
        block.text
        for block in section.blocks
        if block.kind is not BlockKind.FIGURE and block.text is not None
    )
