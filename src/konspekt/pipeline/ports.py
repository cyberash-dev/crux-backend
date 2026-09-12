from dataclasses import dataclass

from konspekt.features.compose.ports.outbound.pdf_compiler import PdfCompilerPort
from konspekt.features.factcheck.ports.outbound.factcheck_llm import (
    ClaimExtractionPort,
    ClaimVerificationPort,
)
from konspekt.features.ingest.ports.outbound.media_tools import MediaToolPort
from konspekt.features.notes.ports.outbound.notes_llm import (
    ExternalImagePort,
    ImageGenerationPort,
    ImageSearchPort,
    SectionCompositionPort,
    VisionCheckPort,
)
from konspekt.features.quiz.ports.outbound.quiz_llm import QuizGenerationPort
from konspekt.features.segmentation.ports.outbound.segmentation_llm import (
    SegmentationLlmPort,
)
from konspekt.features.transcription.ports.outbound.transcription import (
    TranscriptionPort,
)
from konspekt.features.visual.ports.outbound.frame_tools import (
    FrameCapturePort,
    LayoutDetectionPort,
    OcrPort,
)


@dataclass(frozen=True, slots=True)
class PipelinePorts:
    media_tools: MediaToolPort
    transcription: TranscriptionPort
    frame_capture: FrameCapturePort
    ocr: OcrPort
    layout_detection: LayoutDetectionPort
    segmentation_llm: SegmentationLlmPort
    claim_extraction: ClaimExtractionPort
    claim_verification: ClaimVerificationPort
    notes_composition: SectionCompositionPort
    external_images: ExternalImagePort
    image_search: ImageSearchPort
    image_generation: ImageGenerationPort
    vision_check: VisionCheckPort
    quiz_generation: QuizGenerationPort
    pdf_compiler: PdfCompilerPort
