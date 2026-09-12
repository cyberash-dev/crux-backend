import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from konspekt.features.compose.application.compose_pdf import compose_pdf
from konspekt.pipeline.lecture_metrics import build_lecture_metrics
from konspekt.features.compose.application.export_markdown import export_markdown_bundle
from konspekt.features.compose.application.markdown_markup import render_markdown_bundle
from konspekt.features.factcheck.application.artifact import (
    claims_payload,
    parse_claims_payload,
)
from konspekt.features.factcheck.application.check_claims import check_claims
from konspekt.features.ingest.application.artifact import (
    media_payload,
    parse_media_payload,
)
from konspekt.features.ingest.domain.media import LectureMedia
from konspekt.features.notes.application.artifact import (
    notes_payload,
    parse_notes_payload,
    parse_verified_additions,
    verified_additions_payload,
)
from konspekt.features.notes.application.compose_notes import SectionedNotesComposer
from konspekt.features.notes.application.verify_additions import AdditionVerifier
from konspekt.features.notes.application.resolve_illustrations import IllustrationResolver
from konspekt.features.notes.domain.illustration import IllustrationConfig
from konspekt.features.quiz.application.artifact import parse_quiz_payload, quiz_payload
from konspekt.features.quiz.application.generate_quiz import generate_quiz
from konspekt.features.quiz.domain.quiz import QuizConfig
from konspekt.features.segmentation.application.artifact import (
    parse_segmentation_payload,
    segmentation_payload,
)
from konspekt.features.segmentation.application.core_text import core_text
from konspekt.features.segmentation.application.segment_lecture import segment_lecture
from konspekt.features.segmentation.domain.segments import SpanLabel
from konspekt.features.transcription.application.artifact import (
    parse_transcript_payload,
    transcript_payload,
)
from konspekt.features.visual.application.artifact import (
    frames_payload,
    parse_frames_payload,
)
from konspekt.features.visual.application.extract_frames import extract_frames
from konspekt.features.visual.domain.frame import Frame, VisualConfig
from konspekt.pipeline.notes_enrichment import (
    normalize_figure_paths,
    with_factcheck_sources,
    with_work_dir_relative_figures,
    without_duplicate_external_figures,
)
from konspekt.pipeline.ports import PipelinePorts
from konspekt.pipeline.quiz_export import build_quiz_export
from konspekt.pipeline.run_config import RunConfig
from konspekt.pipeline.stage_runner import ArtifactStore, StageRunner
from konspekt.shared.budget import BudgetAccountant

SCHEMA_VERSION = 1


def run_pipeline(
    config: RunConfig, ports: PipelinePorts, budget: BudgetAccountant
) -> Path:
    work_dir = config.work_dir
    work_dir.mkdir(parents=True, exist_ok=True)
    runner = StageRunner(store=ArtifactStore(work_dir), force_from=config.force_from)
    video_digest = _file_digest(config.video_path)
    language_hint = None if config.language == "auto" else config.language
    visual_config = VisualConfig()

    media_raw = runner.run(
        "ingest",
        SCHEMA_VERSION,
        [video_digest],
        {"audio_codec": "opus-32k-16khz-mono"},
        lambda: media_payload(_ingest(config, ports, work_dir)),
    )
    media = parse_media_payload(media_raw)
    audio_path = _resolved(media.audio_path, work_dir)

    transcript_raw = runner.run(
        "transcription",
        SCHEMA_VERSION,
        [_file_digest(audio_path)],
        {"provider": "elevenlabs", "language": config.language},
        lambda: transcript_payload(ports.transcription.transcribe(audio_path, language_hint)),
    )
    transcript = parse_transcript_payload(transcript_raw)

    frames_raw = runner.run(
        "visual",
        SCHEMA_VERSION,
        [video_digest],
        asdict(visual_config),
        lambda: _visual_payload(config, ports, work_dir, visual_config, media.duration_seconds),
    )
    frames = _relative_frames(parse_frames_payload(frames_raw), work_dir)

    budget.ensure_not_exhausted()
    segments_raw = runner.run(
        "segmentation",
        SCHEMA_VERSION,
        [_payload_digest(transcript_raw)],
        {"model": config.models.segmentation},
        lambda: segmentation_payload(segment_lecture(transcript, ports.segmentation_llm)),
    )
    segmentation = parse_segmentation_payload(segments_raw)
    lecture_core_text = core_text(transcript, segmentation)

    budget.ensure_not_exhausted()
    claims_raw = runner.run(
        "factcheck",
        SCHEMA_VERSION,
        [_payload_digest(segments_raw)],
        {"model": config.models.factcheck},
        lambda: claims_payload(
            check_claims(
                lecture_core_text,
                transcript.language,
                ports.claim_extraction,
                ports.claim_verification,
            )
        ),
    )
    claims = list(parse_claims_payload(claims_raw))

    budget.ensure_not_exhausted()
    illustration_config = IllustrationConfig(
        commons_candidates=config.commons_candidates,
        allow_generation=config.generated_images,
    )
    images_dir = work_dir / "images"
    composer = SectionedNotesComposer(
        section_port=ports.notes_composition,
        external_images=ports.external_images,
        images_dir=str(images_dir),
        illustration_resolver=IllustrationResolver(
            search=ports.image_search,
            downloader=ports.external_images,
            generator=ports.image_generation,
            vision=ports.vision_check,
            images_dir=str(images_dir),
            config=illustration_config,
        ),
        addition_verifier=AdditionVerifier(verification=ports.claim_verification),
    )

    def _composed_notes_payload() -> dict[str, Any]:
        composed = composer.compose(transcript, segmentation, claims, list(frames))
        enriched = without_duplicate_external_figures(
            with_work_dir_relative_figures(
                with_factcheck_sources(
                    normalize_figure_paths(composed.notes, frames), claims
                ),
                work_dir,
            )
        )
        payload = notes_payload(enriched)
        payload["verified_additions"] = verified_additions_payload(
            composed.verified_additions
        )
        return payload

    notes_raw = runner.run(
        "notes",
        SCHEMA_VERSION,
        [_payload_digest(segments_raw), _payload_digest(claims_raw), _payload_digest(frames_raw)],
        {
            "model": config.models.notes,
            "composition": "sectioned-structured-verified",
            "illustrations": asdict(illustration_config),
        },
        _composed_notes_payload,
    )
    notes = without_duplicate_external_figures(
        normalize_figure_paths(parse_notes_payload(notes_raw, claims_count=len(claims)), frames)
    )
    verified_additions = parse_verified_additions(notes_raw)

    budget.ensure_not_exhausted()
    quiz_config = QuizConfig()
    quiz_raw = runner.run(
        "quiz",
        SCHEMA_VERSION,
        [_payload_digest(notes_raw)],
        {"model": config.models.quiz, "target": quiz_config.target_for(len(notes.sections))},
        lambda: quiz_payload(generate_quiz(notes, quiz_config, ports.quiz_generation)),
    )
    quiz = parse_quiz_payload(quiz_raw)

    lecture_metrics = build_lecture_metrics(
        duration_seconds=media.duration_seconds,
        spans=segmentation.spans,
        notes=notes,
        claims=claims,
        verified_additions=verified_additions,
        quiz=quiz,
    )
    runner.run(
        "compose",
        SCHEMA_VERSION,
        [_payload_digest(notes_raw), _payload_digest(claims_raw), _payload_digest(quiz_raw)],
        {"cover": "evidence-summary"},
        lambda: {
            "pdf_path": str(
                compose_pdf(
                    notes,
                    config.video_path.name,
                    datetime.now(UTC).date().isoformat(),
                    work_dir,
                    ports.pdf_compiler,
                    lecture_metrics,
                )
            )
        },
    )

    final_pdf = config.lecture_dir / "konspekt.pdf"
    final_pdf.write_bytes((work_dir / "konspekt.pdf").read_bytes())
    quiz_export = build_quiz_export(quiz, notes)
    (config.lecture_dir / "quiz.json").write_text(
        json.dumps(quiz_export, ensure_ascii=False, indent=2)
    )
    export_markdown_bundle(
        render_markdown_bundle(
            notes,
            claims,
            [span for span in segmentation.spans if span.label is not SpanLabel.CORE],
            config.video_path.name,
            datetime.now(UTC).date().isoformat(),
            lecture_metrics,
            verified_additions,
        ),
        config.lecture_dir / "md",
        work_dir,
    )
    return final_pdf


def _visual_payload(
    config: RunConfig,
    ports: PipelinePorts,
    work_dir: Path,
    visual_config: VisualConfig,
    duration_seconds: float,
) -> dict[str, Any]:
    (work_dir / "images").mkdir(parents=True, exist_ok=True)
    extraction = extract_frames(
        config.video_path,
        work_dir / "frames",
        visual_config,
        ports.frame_capture,
        ports.ocr,
        ports.layout_detection,
        duration_seconds,
    )
    return frames_payload(
        _relative_frames(list(extraction.frames), work_dir), extraction.content_box
    )


def _ingest(config: RunConfig, ports: PipelinePorts, work_dir: Path) -> LectureMedia:
    duration = ports.media_tools.probe_duration(config.video_path)
    audio = ports.media_tools.extract_audio(config.video_path, work_dir / "audio.ogg")
    return LectureMedia(
        video_path=config.video_path,
        audio_path=Path(audio.name),
        duration_seconds=duration,
    )


def _relative_frames(frames: list[Frame], work_dir: Path) -> list[Frame]:
    return [
        Frame(
            timestamp_seconds=frame.timestamp_seconds,
            image_path=_work_dir_relative(frame.image_path, work_dir),
            dhash=frame.dhash,
            ocr_text=frame.ocr_text,
        )
        for frame in frames
    ]


def _work_dir_relative(image_path: Path, work_dir: Path) -> Path:
    for base in (work_dir, work_dir.resolve()):
        if image_path.is_relative_to(base):
            return image_path.relative_to(base)
    return image_path


def _resolved(path: Path, work_dir: Path) -> Path:
    return path if path.is_absolute() else work_dir / path


def _file_digest(path: Path) -> bytes:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").digest()


def _payload_digest(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
