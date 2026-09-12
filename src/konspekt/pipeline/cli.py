import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from konspekt.features.factcheck.application.evidence_grounded_verification import (
    EvidenceGroundedVerification,
)
from konspekt.features.factcheck.ports.outbound.claim_translation import ClaimTranslationPort
from konspekt.features.factcheck.ports.outbound.evidence_judge import EvidenceJudgePort
from konspekt.features.factcheck.ports.outbound.search_credential_error import (
    SearchCredentialError,
)
from konspekt.pipeline.orchestrator import run_pipeline
from konspekt.pipeline.ports import PipelinePorts
from konspekt.pipeline.run_config import DEFAULT_MAX_LLM_USD, RunConfig
from konspekt.shared.budget import BudgetAccountant, BudgetExceededError

PortsFactory = Callable[[RunConfig, BudgetAccountant], PipelinePorts]


def default_ports_factory(config: RunConfig, budget: BudgetAccountant) -> PipelinePorts:
    from konspekt.features.compose.adapters.outbound.typst_compiler import TypstCompiler
    from konspekt.features.ingest.adapters.outbound.ffmpeg_tools import FfmpegMediaTools
    from konspekt.features.notes.adapters.outbound.codex_image_generation import (
        CodexImageGeneration,
    )
    from konspekt.features.notes.adapters.outbound.httpx_image_downloader import (
        HttpxExternalImages,
    )
    from konspekt.features.notes.adapters.outbound.wikimedia_commons_search import (
        WikimediaCommonsSearch,
    )
    from konspekt.features.visual.adapters.outbound.ffmpeg_frames import (
        FfmpegFrameCapture,
    )
    from konspekt.features.visual.adapters.outbound.tesseract_ocr import TesseractOcr

    return PipelinePorts(
        media_tools=FfmpegMediaTools(),
        transcription=_transcriber(config),
        frame_capture=FfmpegFrameCapture(),
        ocr=TesseractOcr(),
        external_images=HttpxExternalImages(),
        image_search=WikimediaCommonsSearch(),
        image_generation=CodexImageGeneration(),
        pdf_compiler=TypstCompiler(),
        **_llm_ports(config, budget),
    )


def _transcriber(config: RunConfig):  # noqa: ANN202
    if config.transcriber == "whisper":
        from konspekt.features.transcription.adapters.outbound.whisper_transcriber import (
            WhisperTranscriber,
        )

        return WhisperTranscriber(model_size="large-v3")
    from elevenlabs.client import ElevenLabs

    from konspekt.features.transcription.adapters.outbound.elevenlabs_transcriber import (
        ElevenLabsTranscriber,
    )

    return ElevenLabsTranscriber(client=ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"]))


def _evidence_verification(
    translation: ClaimTranslationPort, judge: EvidenceJudgePort
) -> EvidenceGroundedVerification:
    from konspekt.features.factcheck.adapters.outbound.exa_evidence_search import (
        ExaEvidenceSearch,
    )

    return EvidenceGroundedVerification(
        search=ExaEvidenceSearch(api_key=os.environ["EXA_API_KEY"]),
        translation=translation,
        judge=judge,
    )


def _llm_ports(config: RunConfig, budget: BudgetAccountant) -> dict[str, object]:
    if config.llm_provider == "claude-cli":
        from konspekt.features.factcheck.adapters.outbound.claude_cli_claim_translation import (
            ClaudeCliClaimTranslation,
        )
        from konspekt.features.factcheck.adapters.outbound.claude_cli_evidence_judge import (
            ClaudeCliEvidenceJudge,
        )
        from konspekt.features.factcheck.adapters.outbound.claude_cli_factcheck import (
            ClaudeCliClaimExtraction,
        )
        from konspekt.features.notes.adapters.outbound.claude_cli_notes import (
            ClaudeCliNotesComposition,
        )
        from konspekt.features.notes.adapters.outbound.claude_cli_vision_check import (
            ClaudeCliVisionCheck,
        )
        from konspekt.features.quiz.adapters.outbound.claude_cli_quiz import (
            ClaudeCliQuizGeneration,
        )
        from konspekt.features.segmentation.adapters.outbound.claude_cli_segmentation import (
            ClaudeCliSegmentation,
        )
        from konspekt.features.visual.adapters.outbound.claude_cli_layout import (
            ClaudeCliLayoutDetection,
        )

        return {
            "layout_detection": ClaudeCliLayoutDetection(
                budget=budget, model=config.models.segmentation
            ),
            "vision_check": ClaudeCliVisionCheck(budget=budget, model=config.models.notes),
            "segmentation_llm": ClaudeCliSegmentation(
                budget=budget, model=config.models.segmentation
            ),
            "claim_extraction": ClaudeCliClaimExtraction(
                budget=budget, model=config.models.factcheck
            ),
            "claim_verification": _evidence_verification(
                translation=ClaudeCliClaimTranslation(
                    budget=budget, model=config.models.factcheck
                ),
                judge=ClaudeCliEvidenceJudge(budget=budget, model=config.models.factcheck),
            ),
            "notes_composition": ClaudeCliNotesComposition(
                budget=budget, model=config.models.notes, frames_root=config.work_dir
            ),
            "quiz_generation": ClaudeCliQuizGeneration(budget=budget, model=config.models.quiz),
        }
    from konspekt.features.factcheck.adapters.outbound.claude_claim_translation import (
        ClaudeClaimTranslation,
    )
    from konspekt.features.factcheck.adapters.outbound.claude_evidence_judge import (
        ClaudeEvidenceJudge,
    )
    from konspekt.features.factcheck.adapters.outbound.claude_factcheck import (
        ClaudeClaimExtraction,
    )
    from konspekt.features.notes.adapters.outbound.claude_notes import (
        ClaudeNotesComposition,
    )
    from konspekt.features.notes.adapters.outbound.no_vision_check import NoVisionCheck
    from konspekt.features.quiz.adapters.outbound.claude_quiz import ClaudeQuizGeneration
    from konspekt.features.segmentation.adapters.outbound.claude_segmentation import (
        ClaudeSegmentation,
    )
    from konspekt.features.visual.adapters.outbound.claude_cli_layout import (
        NoLayoutDetection,
    )

    return {
        "layout_detection": NoLayoutDetection(),
        "vision_check": NoVisionCheck(),
        "segmentation_llm": ClaudeSegmentation(budget=budget, model=config.models.segmentation),
        "claim_extraction": ClaudeClaimExtraction(budget=budget, model=config.models.factcheck),
        "claim_verification": _evidence_verification(
            translation=ClaudeClaimTranslation(budget=budget, model=config.models.factcheck),
            judge=ClaudeEvidenceJudge(budget=budget, model=config.models.factcheck),
        ),
        "notes_composition": ClaudeNotesComposition(budget=budget, model=config.models.notes),
        "quiz_generation": ClaudeQuizGeneration(budget=budget, model=config.models.quiz),
    }


def create_app(
    ports_factory: PortsFactory = default_ports_factory,
    claude_binary: str = "claude",
) -> typer.Typer:
    app = typer.Typer(add_completion=False)

    @app.callback()
    def konspekt() -> None:
        """Lecture video to fact-checked study notes PDF with a self-check quiz."""

    @app.command()
    def build(
        video: Annotated[Path, typer.Argument(help="path to the lecture video file")],
        out: Annotated[Path, typer.Option("--out", "-o", help="output directory")] = Path("out"),
        lang: Annotated[str, typer.Option("--lang", help="auto | ru | en")] = "auto",
        force_from: Annotated[
            str | None, typer.Option("--force-from", help="re-run from this stage")
        ] = None,
        max_llm_usd: Annotated[
            float, typer.Option("--max-llm-usd", help="LLM spend budget per run, USD")
        ] = DEFAULT_MAX_LLM_USD,
        llm_provider: Annotated[
            str, typer.Option("--llm-provider", help="claude-cli | api")
        ] = "claude-cli",
        transcriber: Annotated[
            str, typer.Option("--transcriber", help="elevenlabs | whisper")
        ] = "elevenlabs",
        commons_candidates: Annotated[
            int,
            typer.Option(
                "--commons-candidates", min=1,
                help="Wikimedia Commons candidates graded per illustration request",
            ),
        ] = 6,
        generated_images: Annotated[
            bool,
            typer.Option(
                "--generated-images/--no-generated-images",
                help="allow AI image generation when no perfect Commons candidate exists",
            ),
        ] = False,
    ) -> None:
        _validate_invocation(video, lang, llm_provider, transcriber, claude_binary)
        config = RunConfig(
            video_path=video,
            out_dir=out,
            language=lang,
            force_from=force_from,
            max_llm_usd=max_llm_usd,
            llm_provider=llm_provider,
            transcriber=transcriber,
            commons_candidates=commons_candidates,
            generated_images=generated_images,
        )
        budget = BudgetAccountant(max_usd=max_llm_usd)
        try:
            pdf_path = run_pipeline(config, ports_factory(config, budget), budget)
        except BudgetExceededError as error:
            typer.echo(f"error: {error}", err=True)
            typer.echo(f"total spend: {budget.spent_usd:.2f} USD")
            raise typer.Exit(code=1) from error
        except SearchCredentialError as error:
            typer.echo(f"error: search provider rejected EXA_API_KEY: {error}", err=True)
            raise typer.Exit(code=2) from error
        except Exception as error:
            typer.echo(f"error: {error}", err=True)
            raise typer.Exit(code=1) from error
        typer.echo(f"done: {pdf_path}")
        typer.echo(f"total spend: {budget.spent_usd:.2f} USD")

    return app


def _validate_invocation(
    video: Path, lang: str, llm_provider: str, transcriber: str, claude_binary: str
) -> None:
    if not video.is_file():
        typer.echo(f"error: video file not found: {video}", err=True)
        raise typer.Exit(code=2)
    if lang not in ("auto", "ru", "en"):
        typer.echo(f"error: --lang must be auto, ru or en, got {lang!r}", err=True)
        raise typer.Exit(code=2)
    if llm_provider not in ("claude-cli", "api"):
        typer.echo(f"error: --llm-provider must be claude-cli or api, got {llm_provider!r}", err=True)
        raise typer.Exit(code=2)
    if transcriber not in ("elevenlabs", "whisper"):
        typer.echo(f"error: --transcriber must be elevenlabs or whisper, got {transcriber!r}", err=True)
        raise typer.Exit(code=2)
    required_keys = []
    if transcriber == "elevenlabs":
        required_keys.append("ELEVENLABS_API_KEY")
    if llm_provider == "api":
        required_keys.append("ANTHROPIC_API_KEY")
    required_keys.append("EXA_API_KEY")
    missing = [key for key in required_keys if not os.environ.get(key)]
    if missing:
        typer.echo(f"error: missing required env vars: {', '.join(missing)}", err=True)
        raise typer.Exit(code=2)
    if llm_provider == "claude-cli" and shutil.which(claude_binary) is None:
        typer.echo(
            f"error: claude binary not found ({claude_binary}); install Claude Code and log in",
            err=True,
        )
        raise typer.Exit(code=2)


app = create_app()


def main() -> None:
    sys.exit(app())
