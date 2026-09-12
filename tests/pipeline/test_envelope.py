# @covers pipeline:CON-002
import json

import pytest

from konspekt.pipeline.envelope import (
    STAGES,
    ArtifactEnvelope,
    EnvelopeParseError,
    compute_fingerprint,
    parse_envelope,
)


def an_envelope(stage: str = "ingest") -> ArtifactEnvelope:
    return ArtifactEnvelope(
        schema_version=1,
        stage=stage,
        input_fingerprint="a" * 64,
        created_at="2026-08-19T12:00:00Z",
        payload={"key": "value"},
    )


@pytest.mark.parametrize("stage", STAGES)
def test_round_trip_preserves_every_stage(stage: str) -> None:
    envelope = an_envelope(stage=stage)

    restored = parse_envelope(envelope.to_json())

    assert restored == envelope


def test_missing_field_is_rejected() -> None:
    raw = json.loads(an_envelope().to_json())
    del raw["input_fingerprint"]

    with pytest.raises(EnvelopeParseError, match="input_fingerprint"):
        parse_envelope(json.dumps(raw))


def test_unknown_stage_is_rejected() -> None:
    raw = json.loads(an_envelope().to_json())
    raw["stage"] = "mixing"

    with pytest.raises(EnvelopeParseError, match="stage"):
        parse_envelope(json.dumps(raw))


def test_malformed_json_is_rejected() -> None:
    with pytest.raises(EnvelopeParseError, match="not valid JSON"):
        parse_envelope("{not json")


def test_fingerprint_is_deterministic_and_config_sensitive() -> None:
    inputs = [b"artifact-one", b"artifact-two"]

    same = compute_fingerprint(inputs, {"model": "claude-opus-5", "lang": "ru"})
    repeat = compute_fingerprint(inputs, {"lang": "ru", "model": "claude-opus-5"})
    changed_config = compute_fingerprint(inputs, {"model": "claude-opus-5", "lang": "en"})
    changed_input = compute_fingerprint([b"artifact-one"], {"model": "claude-opus-5", "lang": "ru"})

    assert same == repeat
    assert len(same) == 64
    assert same != changed_config
    assert same != changed_input
