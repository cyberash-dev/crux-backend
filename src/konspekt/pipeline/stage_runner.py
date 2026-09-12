import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from konspekt.pipeline.envelope import (
    STAGES,
    ArtifactEnvelope,
    EnvelopeParseError,
    compute_fingerprint,
    parse_envelope,
)

logger = logging.getLogger(__name__)


class ArtifactStore:
    def __init__(self, work_dir: Path) -> None:
        self._work_dir = work_dir

    def path_for(self, stage: str) -> Path:
        ordinal = STAGES.index(stage) + 1
        return self._work_dir / f"{ordinal:02d}-{stage}.json"

    def load(self, stage: str) -> ArtifactEnvelope | None:
        path = self.path_for(stage)
        if not path.exists():
            return None
        try:
            return parse_envelope(path.read_text())
        except EnvelopeParseError:
            return None

    def save(
        self, stage: str, schema_version: int, input_fingerprint: str, payload: dict[str, Any]
    ) -> ArtifactEnvelope:
        envelope = ArtifactEnvelope(
            schema_version=schema_version,
            stage=stage,
            input_fingerprint=input_fingerprint,
            created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            payload=payload,
        )
        self._work_dir.mkdir(parents=True, exist_ok=True)
        self.path_for(stage).write_text(envelope.to_json())
        return envelope


class StageRunner:
    def __init__(self, store: ArtifactStore, force_from: str | None = None) -> None:
        self._store = store
        self._forced_from_index = STAGES.index(force_from) if force_from else None

    def run(
        self,
        stage: str,
        schema_version: int,
        input_artifacts: list[bytes],
        stage_config: Mapping[str, Any],
        produce: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        fingerprint = compute_fingerprint(input_artifacts, stage_config)
        if not self._is_forced(stage):
            stored = self._store.load(stage)
            if (
                stored is not None
                and stored.input_fingerprint == fingerprint
                and stored.schema_version == schema_version
            ):
                logger.info("stage.skipped", extra={"stage": stage, "reason": "fingerprint match"})
                return stored.payload
        payload = produce()
        self._store.save(stage, schema_version, fingerprint, payload)
        logger.info("stage.completed", extra={"stage": stage})
        return payload

    def _is_forced(self, stage: str) -> bool:
        if self._forced_from_index is None:
            return False
        return STAGES.index(stage) >= self._forced_from_index
