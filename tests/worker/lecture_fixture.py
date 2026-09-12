import json
from pathlib import Path

from konspekt.pipeline.envelope import STAGES

LECTURE_TITLE = "Introduction to Algorithms: Problems, Correctness, Efficiency"

SEGMENTATION_PAYLOAD = {
    "lecture_title": LECTURE_TITLE,
    "sections_plan": [
        {
            "section_id": "s1",
            "title": "Course Introduction and Goals",
            "start_seconds": 0.0,
            "end_seconds": 179.0,
            "subsections": [],
        }
    ],
    "spans": [
        {"start_seconds": 0.0, "end_seconds": 179.0, "label": "core",
         "section_id": "s1", "reason": None},
        {"start_seconds": 179.0, "end_seconds": 201.0, "label": "logistics",
         "section_id": None, "reason": "problem set deadlines"},
    ],
}

FACTCHECK_CLAIMS = [
    {
        "claim_id": "c_000",
        "claim_text": "If there are more than 365 of you, two of you must share a birthday.",
        "span_start_seconds": 369,
        "span_end_seconds": 465,
        "verdict": "mixed",
        "sources": ["https://brilliant.org/wiki/birthday-paradox/"],
        "annotation": "Counting February 29 gives 366 pigeonholes, so 367 people are needed.",
        "corrected_text": None,
    },
    {
        "claim_id": "c_001",
        "claim_text": "A pair becomes likely once the space exceeds the square of the class size.",
        "span_start_seconds": 369,
        "span_end_seconds": 465,
        "verdict": "unverified",
        "sources": ["https://en.wikipedia.org/wiki/Birthday_problem"],
        "annotation": None,
        "corrected_text": None,
    },
]


def a_prose_block(text: str) -> dict[str, object]:
    return {
        "kind": "prose", "text": text, "term": None, "image_path": None, "caption": None,
        "source_ref": None, "claim_ref": None, "provenance": None, "origin": None,
        "table": None, "diagram": None, "chart": None,
    }


NOTES_SECTION = {
    "section_id": "s1",
    "title": "Course Introduction and Goals",
    "source_spans": [[0.0, 179.0]],
    "subsections": [
        {
            "section_id": "s1.1",
            "title": "Instructors and Course Overview",
            "source_spans": [[0.0, 48.0]],
            "subsections": [],
            "blocks": [a_prose_block("The material builds in layers.")],
        }
    ],
    "blocks": [a_prose_block("An introductory course in algorithms asks one question.")],
}

NOTES_PAYLOAD = {
    "title": LECTURE_TITLE,
    "language": "en",
    "sections": [NOTES_SECTION],
    "verified_additions": [],
}

QUIZ_EXPORT = {
    "format_version": 2,
    "lecture_title": LECTURE_TITLE,
    "language": "en",
    "questions": [
        {
            "question_id": "q1",
            "type": "single_choice",
            "prompt": "What must accompany a solution in the theoretical study of algorithms?",
            "options": ["A stopwatch measurement", "Arguments for correctness and efficiency"],
            "correct_options": [1],
            "model_answer": None,
            "rubric": None,
            "time_range": {"start_seconds": 48.0, "end_seconds": 179.0},
            "section_id": "s1.1",
            "section_title": "Instructors and Course Overview",
        }
    ],
}

PDF_BYTES = b"%PDF-1.7 konspekt"
MARKDOWN_BYTES = b"# Introduction to Algorithms\n\n![Goals](md/images/frame_125125.jpg)\n"
JPEG_BYTES = b"\xff\xd8\xff\xe0frame"
PNG_BYTES = b"\x89PNG\r\n\x1a\nillustration"

_STAGE_PAYLOADS: dict[str, dict[str, object]] = {
    "segmentation": SEGMENTATION_PAYLOAD,
    "factcheck": {"claims": FACTCHECK_CLAIMS},
    "notes": NOTES_PAYLOAD,
}


def write_stage_artifact(lecture_dir: Path, stage: str) -> None:
    work_dir = lecture_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    envelope = {
        "schema_version": 1,
        "stage": stage,
        "input_fingerprint": "a" * 64,
        "created_at": "2026-09-12T10:00:00Z",
        "payload": _STAGE_PAYLOADS.get(stage, {}),
    }
    ordinal = STAGES.index(stage) + 1
    (work_dir / f"{ordinal:02d}-{stage}.json").write_text(json.dumps(envelope))


def write_final_outputs(lecture_dir: Path) -> None:
    write_stage_artifact(lecture_dir, "compose")
    (lecture_dir / "konspekt.pdf").write_bytes(PDF_BYTES)
    (lecture_dir / "konspekt.md").write_bytes(MARKDOWN_BYTES)
    (lecture_dir / "quiz.json").write_text(json.dumps(QUIZ_EXPORT))
    images_dir = lecture_dir / "md" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "frame_125125.jpg").write_bytes(JPEG_BYTES)
    (images_dir / "illustration_s1.png").write_bytes(PNG_BYTES)
