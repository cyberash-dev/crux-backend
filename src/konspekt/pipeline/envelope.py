import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

STAGES: tuple[str, ...] = (
    "ingest",
    "transcription",
    "visual",
    "segmentation",
    "factcheck",
    "notes",
    "quiz",
    "compose",
)

_REQUIRED_FIELDS = ("schema_version", "stage", "input_fingerprint", "created_at", "payload")


class EnvelopeParseError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ArtifactEnvelope:
    schema_version: int
    stage: str
    input_fingerprint: str
    created_at: str
    payload: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "stage": self.stage,
                "input_fingerprint": self.input_fingerprint,
                "created_at": self.created_at,
                "payload": self.payload,
            },
            ensure_ascii=False,
            indent=2,
        )


def parse_envelope(raw: str) -> ArtifactEnvelope:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise EnvelopeParseError(f"artifact is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise EnvelopeParseError("artifact root is not a JSON object")
    for field in _REQUIRED_FIELDS:
        if field not in data:
            raise EnvelopeParseError(f"artifact is missing field {field!r}")
    if data["stage"] not in STAGES:
        raise EnvelopeParseError(f"unknown stage {data['stage']!r}")
    return ArtifactEnvelope(
        schema_version=data["schema_version"],
        stage=data["stage"],
        input_fingerprint=data["input_fingerprint"],
        created_at=data["created_at"],
        payload=data["payload"],
    )


def compute_fingerprint(
    input_artifacts: Iterable[bytes], stage_config: Mapping[str, Any]
) -> str:
    digest = hashlib.sha256()
    for artifact_bytes in input_artifacts:
        digest.update(hashlib.sha256(artifact_bytes).digest())
    digest.update(json.dumps(dict(stage_config), sort_keys=True, ensure_ascii=False).encode())
    return digest.hexdigest()
