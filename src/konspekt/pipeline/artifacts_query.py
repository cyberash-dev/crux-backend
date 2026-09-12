import json
from pathlib import Path
from typing import Any

from konspekt.pipeline.envelope import STAGES, EnvelopeParseError, parse_envelope
from konspekt.pipeline.stage_runner import ArtifactStore


class LectureQueryError(Exception):
    pass


def list_lectures(out_dir: Path) -> list[dict[str, Any]]:
    if not out_dir.is_dir():
        return []
    return [
        lecture_status(out_dir, entry.name)
        for entry in sorted(out_dir.iterdir())
        if (entry / "work").is_dir()
    ]


def lecture_status(out_dir: Path, slug: str) -> dict[str, Any]:
    work_dir = _work_dir(out_dir, slug)
    store = ArtifactStore(work_dir)
    stages = {stage: store.load(stage) is not None for stage in STAGES}
    pdf_path = out_dir / slug / "konspekt.pdf"
    quiz_path = out_dir / slug / "quiz.json"
    md_path = out_dir / slug / "md" / "README.md"
    return {
        "slug": slug,
        "stages": stages,
        "stages_done": [stage for stage, done in stages.items() if done],
        "pdf_path": str(pdf_path) if pdf_path.exists() else None,
        "quiz_path": str(quiz_path) if quiz_path.exists() else None,
        "md_path": str(md_path) if md_path.exists() else None,
    }


def load_outline(out_dir: Path, slug: str) -> dict[str, Any]:
    notes = _try_payload(out_dir, slug, "notes")
    if notes is not None:
        return {
            "lecture_title": notes["title"],
            "sections": [_outline_entry_from_notes(section) for section in notes["sections"]],
        }
    plan = _payload(out_dir, slug, "segmentation")
    return {"lecture_title": plan["lecture_title"], "sections": plan["sections_plan"]}


def load_section(out_dir: Path, slug: str, section_id: str) -> dict[str, Any]:
    notes = _payload(out_dir, slug, "notes")
    for section in notes["sections"]:
        for candidate in (section, *section.get("subsections", [])):
            if candidate["section_id"] == section_id:
                return candidate
    raise LectureQueryError(f"section {section_id!r} not found in lecture {slug!r}")


def load_cut_log(out_dir: Path, slug: str) -> list[dict[str, Any]]:
    payload = _payload(out_dir, slug, "segmentation")
    return [
        {
            "start_seconds": span["start_seconds"],
            "end_seconds": span["end_seconds"],
            "label": span["label"],
            "reason": span["reason"],
        }
        for span in payload["spans"]
        if span["label"] != "core"
    ]


def load_claims(
    out_dir: Path, slug: str, verdict: str | None = None
) -> list[dict[str, Any]]:
    claims = _payload(out_dir, slug, "factcheck")["claims"]
    if verdict is None:
        return claims
    return [claim for claim in claims if claim["verdict"] == verdict]


def load_quiz(out_dir: Path, slug: str) -> dict[str, Any]:
    quiz_path = out_dir / slug / "quiz.json"
    if not quiz_path.exists():
        raise LectureQueryError(
            f"quiz export is missing for lecture {slug!r}; run the pipeline to completion"
        )
    return json.loads(quiz_path.read_text())


def _outline_entry_from_notes(section: dict[str, Any]) -> dict[str, Any]:
    spans = section.get("source_spans") or [[0.0, 0.0]]
    return {
        "section_id": section["section_id"],
        "title": section["title"],
        "start_seconds": spans[0][0],
        "end_seconds": spans[-1][1],
        "subsections": [
            _outline_entry_from_notes(subsection)
            for subsection in section.get("subsections", [])
        ],
    }


def _work_dir(out_dir: Path, slug: str) -> Path:
    work_dir = out_dir / slug / "work"
    if not work_dir.is_dir():
        raise LectureQueryError(f"lecture {slug!r} not found under {out_dir}")
    return work_dir


def _try_payload(out_dir: Path, slug: str, stage: str) -> dict[str, Any] | None:
    store = ArtifactStore(_work_dir(out_dir, slug))
    envelope = store.load(stage)
    return envelope.payload if envelope is not None else None


def _payload(out_dir: Path, slug: str, stage: str) -> dict[str, Any]:
    work_dir = _work_dir(out_dir, slug)
    path = ArtifactStore(work_dir).path_for(stage)
    if not path.exists():
        raise LectureQueryError(
            f"stage {stage!r} artifact is missing for lecture {slug!r}; "
            f"run: konspekt build <video> (or --force-from {stage})"
        )
    try:
        return parse_envelope(path.read_text()).payload
    except EnvelopeParseError as error:
        raise LectureQueryError(f"stage {stage!r} artifact is corrupted: {error}") from error
