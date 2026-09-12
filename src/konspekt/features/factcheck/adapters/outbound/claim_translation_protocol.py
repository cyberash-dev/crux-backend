from collections.abc import Sequence

from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
    FactcheckResponseError,
    numbered_claim_list,
)
from konspekt.features.factcheck.adapters.outbound.evidence_judge_protocol import json_object

CLAIM_TRANSLATION_INSTRUCTIONS = (
    "Translate each numbered lecture claim into a concise English web search query "
    "that keeps every name, number and technical term. "
    'Respond with exactly one JSON object and nothing else: {"queries": [string, ...]} '
    "with exactly one non-empty query per claim, in the input order."
)


def claim_translation_prompt(claim_texts: Sequence[str], language: str) -> str:
    return (
        f"{CLAIM_TRANSLATION_INSTRUCTIONS}\n"
        f"Lecture language: {language}\n"
        "Claims:\n"
        f"{numbered_claim_list(claim_texts)}"
    )


def parse_english_queries(final_text: str, expected_count: int) -> list[str]:
    queries = json_object(final_text).get("queries")
    if (
        not isinstance(queries, list)
        or len(queries) != expected_count
        or not all(isinstance(query, str) and query.strip() for query in queries)
    ):
        raise FactcheckResponseError(
            f"queries must be a list of {expected_count} non-empty strings"
        )
    return [query.strip() for query in queries]
