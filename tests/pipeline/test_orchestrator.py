# @covers pipeline:REQ-001
# @covers pipeline:POL-002
import json
from pathlib import Path

import pytest

from konspekt.pipeline.orchestrator import run_pipeline
from konspekt.pipeline.run_config import RunConfig
from konspekt.shared.budget import BudgetAccountant, BudgetExceededError
from tests.pipeline.pipeline_fakes import FakePorts


def a_video(tmp_path: Path) -> Path:
    video = tmp_path / "lecture.mp4"
    video.write_bytes(b"video-bytes")
    return video


def a_config(tmp_path: Path, **overrides: object) -> RunConfig:
    return RunConfig(video_path=a_video(tmp_path), out_dir=tmp_path / "out", **overrides)  # type: ignore[arg-type]


def test_happy_path_produces_pdf_and_all_artifacts(tmp_path: Path) -> None:
    config = a_config(tmp_path)
    fakes = FakePorts()

    pdf_path = run_pipeline(config, fakes.as_ports(), BudgetAccountant(max_usd=15.0))

    assert pdf_path == config.lecture_dir / "konspekt.pdf"
    assert pdf_path.read_bytes().startswith(b"%PDF")
    artifact_names = sorted(p.name for p in config.work_dir.glob("0*.json"))
    assert artifact_names == [
        "01-ingest.json",
        "02-transcription.json",
        "03-visual.json",
        "04-segmentation.json",
        "05-factcheck.json",
        "06-notes.json",
        "07-quiz.json",
        "08-compose.json",
    ]


def test_second_run_skips_every_stage(tmp_path: Path) -> None:
    config = a_config(tmp_path)
    fakes = FakePorts()
    run_pipeline(config, fakes.as_ports(), BudgetAccountant(max_usd=15.0))

    run_pipeline(config, fakes.as_ports(), BudgetAccountant(max_usd=15.0))

    assert fakes.media_tools.calls == 1
    assert fakes.transcription.calls == 1
    assert fakes.segmentation_llm.calls == 1
    assert fakes.notes_composition.calls == 1
    assert fakes.pdf_compiler.calls == 1


def test_exhausted_budget_aborts_before_llm_stage_and_keeps_artifacts(tmp_path: Path) -> None:
    config = a_config(tmp_path)
    fakes = FakePorts()
    exhausted = BudgetAccountant(max_usd=1.0)
    exhausted.charge(1.0)

    with pytest.raises(BudgetExceededError, match="BUDGET_EXCEEDED"):
        run_pipeline(config, fakes.as_ports(), exhausted)

    assert fakes.segmentation_llm.calls == 0
    assert (config.work_dir / "01-ingest.json").exists()
    assert (config.work_dir / "02-transcription.json").exists()


def test_factcheck_note_without_source_is_enriched_from_claims(tmp_path: Path) -> None:
    config = a_config(tmp_path)
    fakes = FakePorts()

    run_pipeline(config, fakes.as_ports(), BudgetAccountant(max_usd=15.0))

    notes_payload = json.loads((config.work_dir / "06-notes.json").read_text())["payload"]
    factcheck_blocks = [
        block
        for section in notes_payload["sections"]
        for block in section["blocks"]
        if block["kind"] == "factcheck_note"
    ]
    assert factcheck_blocks
    assert "https://doi.org/10.1038/248030a0" in factcheck_blocks[0]["text"]


# @covers output:CON-031
def test_quiz_export_file_is_written_next_to_the_pdf(tmp_path: Path) -> None:
    config = a_config(tmp_path)
    fakes = FakePorts()

    run_pipeline(config, fakes.as_ports(), BudgetAccountant(max_usd=15.0))

    export = json.loads((config.lecture_dir / "quiz.json").read_text())
    stored_quiz = json.loads((config.work_dir / "07-quiz.json").read_text())["payload"]
    assert export["format_version"] == 2
    assert [q["question_id"] for q in export["questions"]] == [
        q["question_id"] for q in stored_quiz["questions"]
    ]
    assert all(q["section_title"] for q in export["questions"])


def test_factcheck_sources_are_appended_inside_subsections() -> None:
    from konspekt.features.factcheck.domain.claims import CheckedClaim, Verdict
    from konspekt.features.notes.domain.notes import (
        BlockKind,
        NoteBlock,
        NoteSection,
        Notes,
    )
    from konspekt.pipeline.notes_enrichment import with_factcheck_sources
    from konspekt.shared.timecode import TimeRange

    claims = [
        CheckedClaim(
            claim_text="x",
            span=TimeRange(0.0, 1.0),
            verdict=Verdict.DISPUTED,
            sources=("https://doi.org/10.1/abc",),
            annotation="расходится",
        )
    ]
    notes = Notes(
        title="t",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="s",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=(),
                subsections=(
                    NoteSection(
                        section_id="s1.1",
                        title="sub",
                        source_spans=(TimeRange(0.0, 30.0),),
                        blocks=(
                            NoteBlock(
                                kind=BlockKind.FACTCHECK_NOTE,
                                text="Аннотация без ссылки.",
                                claim_ref=0,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    enriched = with_factcheck_sources(notes, claims)

    text = enriched.sections[0].subsections[0].blocks[0].text
    assert "https://doi.org/10.1/abc" in text


# @covers extraction:REQ-011
def test_detected_content_box_reaches_capture_and_the_visual_artifact(tmp_path: Path) -> None:
    from tests.pipeline.pipeline_fakes import FakeLayoutDetection

    config = a_config(tmp_path)
    fakes = FakePorts(layout_detection=FakeLayoutDetection(box=None))

    run_pipeline(config, fakes.as_ports(), BudgetAccountant(max_usd=15.0))

    visual = json.loads((config.work_dir / "03-visual.json").read_text())["payload"]
    assert visual["content_box"] is None
    assert fakes.frame_capture.received_boxes == [None]


# @covers analysis:REQ-027
def test_confirmed_commons_illustration_is_stored_relative_to_the_work_dir(tmp_path: Path) -> None:
    from konspekt.features.notes.domain.illustration import IllustrationRequest
    from konspekt.features.notes.ports.outbound.notes_llm import ImageCandidate
    from tests.pipeline.pipeline_fakes import FakeImageSearch, FakeSectionComposition

    config = a_config(tmp_path)
    fakes = FakePorts(
        notes_composition=FakeSectionComposition(
            illustration_request=IllustrationRequest(
                purpose="Схема испарения чёрной дыры",
                search_query="black hole evaporation diagram",
                generation_prompt="Educational diagram of black hole evaporation",
                insert_index=1,
            )
        ),
        image_search=FakeImageSearch(
            candidates=(
                ImageCandidate(
                    file_page_url="https://commons.wikimedia.org/wiki/File:Hawking.jpg",
                    image_url="https://upload.wikimedia.org/x/Hawking.jpg",
                ),
            )
        ),
    )

    run_pipeline(config, fakes.as_ports(), BudgetAccountant(max_usd=15.0))

    notes = json.loads((config.work_dir / "06-notes.json").read_text())["payload"]
    figures = [
        block
        for section in notes["sections"]
        for block in section["blocks"]
        if block["kind"] == "figure"
    ]
    assert len(figures) == 1
    assert figures[0]["provenance"] == "commons"
    assert figures[0]["source_ref"] == "https://commons.wikimedia.org/wiki/File:Hawking.jpg"
    assert figures[0]["image_path"] == "images/commons.jpg"
    assert (config.work_dir / "images" / "commons.jpg").exists()


# @covers output:CON-032
def test_markdown_bundle_is_written_next_to_the_pdf(tmp_path: Path) -> None:
    config = a_config(tmp_path)

    run_pipeline(config, FakePorts().as_ports(), BudgetAccountant(max_usd=15.0))

    md_dir = config.lecture_dir / "md"
    readme = (md_dir / "README.md").read_text()
    notes = json.loads((config.work_dir / "06-notes.json").read_text())["payload"]
    section_files = sorted((md_dir / "sections").glob("*.md"))
    assert len(section_files) == len(notes["sections"])
    for section_file in section_files:
        assert f"sections/{section_file.name}" in readme
    prose_texts = [
        block["text"]
        for section in notes["sections"]
        for block in section["blocks"]
        if block["kind"] == "prose"
    ]
    section_texts = [section_file.read_text() for section_file in section_files]
    for prose in prose_texts:
        assert sum(text.count(prose) for text in section_texts) == 1
    assert (md_dir / "claims.md").exists() and (md_dir / "cut-log.md").exists()
    assert "байка" in (md_dir / "cut-log.md").read_text()
    combined = (config.lecture_dir / "konspekt.md").read_text()
    for prose in prose_texts:
        assert combined.count(prose) == 1


# @covers analysis:REQ-028
def test_notes_artifact_records_verified_additions(tmp_path: Path) -> None:
    config = a_config(tmp_path)

    run_pipeline(config, FakePorts().as_ports(), BudgetAccountant(max_usd=15.0))

    payload = json.loads((config.work_dir / "06-notes.json").read_text())["payload"]
    additions = payload["verified_additions"]
    assert additions, "fact and definition blocks must be audited"
    assert {addition["kind"] for addition in additions} <= {"fact", "definition"}
    assert all(addition["action"] == "kept" for addition in additions)
    assert all(addition["verdict"] == "confirmed" for addition in additions)
