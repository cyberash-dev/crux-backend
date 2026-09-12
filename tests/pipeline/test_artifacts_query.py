# @covers pipeline:CON-003
import json
from pathlib import Path

import pytest

from konspekt.pipeline.artifacts_query import (
    LectureQueryError,
    lecture_status,
    list_lectures,
    load_claims,
    load_cut_log,
    load_outline,
    load_quiz,
    load_section,
)


def an_envelope(stage: str, payload: dict) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "stage": stage,
            "input_fingerprint": "a" * 64,
            "created_at": "2026-08-20T10:00:00Z",
            "payload": payload,
        }
    )


def a_lecture(tmp_path: Path, slug: str = "lekciya-an-1") -> Path:
    work = tmp_path / slug / "work"
    work.mkdir(parents=True)
    (work / "04-segmentation.json").write_text(
        an_envelope(
            "segmentation",
            {
                "lecture_title": "Введение в анатомию",
                "sections_plan": [
                    {
                        "section_id": "s1",
                        "title": "Клетка",
                        "start_seconds": 0.0,
                        "end_seconds": 600.0,
                        "subsections": [],
                    }
                ],
                "spans": [
                    {"start_seconds": 0.0, "end_seconds": 500.0, "label": "core",
                     "section_id": "s1", "reason": None},
                    {"start_seconds": 500.0, "end_seconds": 600.0, "label": "tangent",
                     "section_id": None, "reason": "байка"},
                ],
            },
        )
    )
    (work / "05-factcheck.json").write_text(
        an_envelope(
            "factcheck",
            {
                "claims": [
                    {"claim_text": "a", "span_start_seconds": 0.0, "span_end_seconds": 1.0,
                     "verdict": "confirmed", "sources": ["https://x"], "annotation": None},
                    {"claim_text": "b", "span_start_seconds": 1.0, "span_end_seconds": 2.0,
                     "verdict": "disputed", "sources": ["https://y"], "annotation": "нет"},
                ]
            },
        )
    )
    (work / "06-notes.json").write_text(
        an_envelope(
            "notes",
            {
                "title": "Введение в анатомию",
                "language": "ru",
                "sections": [
                    {
                        "section_id": "s1",
                        "title": "Клетка",
                        "source_spans": [[0.0, 600.0]],
                        "subsections": [
                            {
                                "section_id": "s1.1",
                                "title": "Органеллы",
                                "source_spans": [[300.0, 600.0]],
                                "subsections": [],
                                "blocks": [
                                    {"kind": "prose", "text": "Про органеллы.", "term": None,
                                     "image_path": None, "caption": None,
                                     "source_ref": None, "claim_ref": None}
                                ],
                            }
                        ],
                        "blocks": [
                            {"kind": "prose", "text": "Про клетку.", "term": None,
                             "image_path": None, "caption": None,
                             "source_ref": None, "claim_ref": None}
                        ],
                    }
                ],
            },
        )
    )
    (tmp_path / slug / "quiz.json").write_text(
        json.dumps({"format_version": 1, "lecture_title": "Введение в анатомию",
                    "language": "ru", "questions": []})
    )
    (tmp_path / slug / "konspekt.pdf").write_bytes(b"%PDF-fake")
    return tmp_path


def test_list_lectures_reports_slug_stages_and_paths(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    lectures = list_lectures(out_dir)

    assert len(lectures) == 1
    lecture = lectures[0]
    assert lecture["slug"] == "lekciya-an-1"
    assert set(lecture["stages_done"]) == {"segmentation", "factcheck", "notes"}
    assert lecture["pdf_path"].endswith("konspekt.pdf")
    assert lecture["quiz_path"].endswith("quiz.json")


def test_lecture_status_marks_missing_stages(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    status = lecture_status(out_dir, "lekciya-an-1")

    assert status["stages"]["notes"] is True
    assert status["stages"]["compose"] is False


def test_unknown_slug_raises_named_error(tmp_path: Path) -> None:
    with pytest.raises(LectureQueryError, match="net-takoy"):
        lecture_status(tmp_path, "net-takoy")


def test_outline_prefers_notes_tree(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    outline = load_outline(out_dir, "lekciya-an-1")

    assert outline["lecture_title"] == "Введение в анатомию"
    assert outline["sections"][0]["subsections"][0]["section_id"] == "s1.1"


def test_outline_falls_back_to_plan_without_notes(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)
    (out_dir / "lekciya-an-1" / "work" / "06-notes.json").unlink()

    outline = load_outline(out_dir, "lekciya-an-1")

    assert outline["lecture_title"] == "Введение в анатомию"
    assert outline["sections"][0]["section_id"] == "s1"


def test_section_lookup_reaches_subsections(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    section = load_section(out_dir, "lekciya-an-1", "s1.1")

    assert section["title"] == "Органеллы"
    assert section["blocks"][0]["text"] == "Про органеллы."


def test_unknown_section_raises_named_error(tmp_path: Path) -> None:
    with pytest.raises(LectureQueryError, match="s9"):
        load_section(a_lecture(tmp_path), "lekciya-an-1", "s9")


def test_cut_log_returns_non_core_spans_only(tmp_path: Path) -> None:
    cut_log = load_cut_log(a_lecture(tmp_path), "lekciya-an-1")

    assert cut_log == [
        {"start_seconds": 500.0, "end_seconds": 600.0, "label": "tangent", "reason": "байка"}
    ]


def test_claims_filter_by_verdict(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)

    disputed = load_claims(out_dir, "lekciya-an-1", verdict="disputed")

    assert [claim["claim_text"] for claim in disputed] == ["b"]
    assert len(load_claims(out_dir, "lekciya-an-1")) == 2


def test_quiz_returns_export_object(tmp_path: Path) -> None:
    quiz = load_quiz(a_lecture(tmp_path), "lekciya-an-1")

    assert quiz["format_version"] == 1


def test_missing_artifact_names_the_stage(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)
    (out_dir / "lekciya-an-1" / "work" / "05-factcheck.json").unlink()

    with pytest.raises(LectureQueryError, match="factcheck"):
        load_claims(out_dir, "lekciya-an-1")


# @covers pipeline:DLT-003
def test_status_reports_markdown_bundle_path_when_present(tmp_path: Path) -> None:
    out_dir = a_lecture(tmp_path)
    assert lecture_status(out_dir, "lekciya-an-1")["md_path"] is None
    (out_dir / "lekciya-an-1" / "md").mkdir()
    (out_dir / "lekciya-an-1" / "md" / "README.md").write_text("# x")

    status = lecture_status(out_dir, "lekciya-an-1")

    assert status["md_path"].endswith("md/README.md")
