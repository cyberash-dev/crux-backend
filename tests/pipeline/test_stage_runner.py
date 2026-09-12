# @covers pipeline:REQ-001
import json
from pathlib import Path

from konspekt.pipeline.stage_runner import ArtifactStore, StageRunner


class CountingProducer:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    def __call__(self) -> dict:
        self.calls += 1
        return self.payload


def a_runner(tmp_path: Path, force_from: str | None = None) -> StageRunner:
    return StageRunner(store=ArtifactStore(work_dir=tmp_path), force_from=force_from)


def test_matching_fingerprint_skips_the_stage(tmp_path: Path) -> None:
    producer = CountingProducer({"value": 1})
    inputs = [b"input"]
    config = {"model": "m1"}
    a_runner(tmp_path).run("ingest", 1, inputs, config, producer)

    payload = a_runner(tmp_path).run("ingest", 1, inputs, config, producer)

    assert producer.calls == 1
    assert payload == {"value": 1}


def test_changed_config_reruns_the_stage(tmp_path: Path) -> None:
    producer = CountingProducer({"value": 1})
    inputs = [b"input"]
    a_runner(tmp_path).run("ingest", 1, inputs, {"model": "m1"}, producer)

    a_runner(tmp_path).run("ingest", 1, inputs, {"model": "m2"}, producer)

    assert producer.calls == 2


def test_missing_artifact_runs_the_stage(tmp_path: Path) -> None:
    producer = CountingProducer({"value": 1})

    a_runner(tmp_path).run("ingest", 1, [b"input"], {}, producer)

    assert producer.calls == 1
    assert (tmp_path / "01-ingest.json").exists()


def test_foreign_schema_version_reruns_the_stage(tmp_path: Path) -> None:
    producer = CountingProducer({"value": 1})
    inputs = [b"input"]
    config: dict = {}
    a_runner(tmp_path).run("ingest", 1, inputs, config, producer)

    a_runner(tmp_path).run("ingest", 2, inputs, config, producer)

    assert producer.calls == 2


def test_corrupted_artifact_reruns_the_stage(tmp_path: Path) -> None:
    producer = CountingProducer({"value": 1})
    inputs = [b"input"]
    config: dict = {}
    a_runner(tmp_path).run("ingest", 1, inputs, config, producer)
    (tmp_path / "01-ingest.json").write_text("{broken")

    a_runner(tmp_path).run("ingest", 1, inputs, config, producer)

    assert producer.calls == 2


def test_force_from_reruns_the_stage_and_the_tail(tmp_path: Path) -> None:
    ingest = CountingProducer({"value": "i"})
    visual = CountingProducer({"value": "v"})
    compose = CountingProducer({"value": "c"})
    first = a_runner(tmp_path)
    first.run("ingest", 1, [b"x"], {}, ingest)
    first.run("visual", 1, [b"x"], {}, visual)
    first.run("compose", 1, [b"x"], {}, compose)

    second = a_runner(tmp_path, force_from="visual")
    second.run("ingest", 1, [b"x"], {}, ingest)
    second.run("visual", 1, [b"x"], {}, visual)
    second.run("compose", 1, [b"x"], {}, compose)

    assert ingest.calls == 1
    assert visual.calls == 2
    assert compose.calls == 2


def test_saved_artifact_is_a_valid_envelope(tmp_path: Path) -> None:
    a_runner(tmp_path).run("quiz", 3, [b"x"], {"n": 10}, CountingProducer({"q": []}))

    raw = json.loads((tmp_path / "07-quiz.json").read_text())

    assert raw["stage"] == "quiz"
    assert raw["schema_version"] == 3
    assert len(raw["input_fingerprint"]) == 64
    assert raw["payload"] == {"q": []}
