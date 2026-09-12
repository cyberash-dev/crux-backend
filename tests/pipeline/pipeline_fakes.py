from dataclasses import dataclass, field
from pathlib import Path

from konspekt.features.factcheck.domain.claims import (
    ExtractedClaim,
    VerificationOutcome,
    Verdict,
)
from konspekt.features.notes.domain.notes import BlockKind, NoteBlock, NoteSection, Notes
from konspekt.features.quiz.domain.quiz import (
    QuestionType,
    Quiz,
    QuizConfig,
    QuizQuestion,
    Rubric,
    RubricConcept,
)
from konspekt.features.notes.domain.illustration import (
    CandidateAssessment,
    IllustrationRequest,
)
from konspekt.features.notes.ports.outbound.notes_llm import (
    ImageCandidate,
    IndexedClaim,
    SectionComposition,
)
from konspekt.features.visual.domain.frame import ContentBox
from konspekt.features.segmentation.domain.segments import (
    LabeledSpan,
    SectionPlanEntry,
    SpanLabel,
)
from konspekt.features.transcription.domain.transcript import (
    Transcript,
    TranscriptSegment,
)
from konspekt.pipeline.ports import PipelinePorts
from konspekt.shared.timecode import TimeRange


@dataclass
class FakeMediaTools:
    calls: int = 0

    def probe_duration(self, video_path: Path) -> float:
        return 10.0

    def extract_audio(self, video_path: Path, audio_dest: Path) -> Path:
        self.calls += 1
        audio_dest.parent.mkdir(parents=True, exist_ok=True)
        audio_dest.write_bytes(b"OggS-fake")
        return audio_dest


@dataclass
class FakeTranscription:
    language: str = "ru"
    calls: int = 0

    def transcribe(self, audio_path: Path, language_hint: str | None) -> Transcript:
        self.calls += 1
        language = language_hint or self.language
        return Transcript(
            language=language,
            segments=(
                TranscriptSegment(TimeRange(0.0, 5.0), "Тема лекции: испарение чёрных дыр.", "s0"),
                TranscriptSegment(TimeRange(5.0, 10.0), "Кстати, забавный случай на конференции.", "s0"),
            ),
        )


@dataclass
class FakeFrameCapture:
    received_boxes: list[ContentBox | None] = field(default_factory=list)

    def capture_candidates(self, video_path, frames_dir, config, content_box):
        self.received_boxes.append(content_box)
        frames_dir.mkdir(parents=True, exist_ok=True)
        return []

    def capture_probes(self, video_path, probes_dir, timestamps) -> list[Path]:
        probes_dir.mkdir(parents=True, exist_ok=True)
        return []


@dataclass
class FakeLayoutDetection:
    box: ContentBox | None = None

    def detect_content_box(self, probe_paths) -> ContentBox | None:
        return self.box


@dataclass
class FakeOcr:
    def read_text(self, image_path: Path) -> str | None:
        return None


@dataclass
class FakeSegmentationLlm:
    calls: int = 0

    def plan_outline(self, transcript: Transcript) -> tuple[str, list[SectionPlanEntry]]:
        self.calls += 1
        return (
            "Испарение чёрных дыр",
            [SectionPlanEntry("s1", "Испарение чёрных дыр", TimeRange(0.0, 10.0))],
        )

    def label_spans(self, transcript, sections_plan) -> list[LabeledSpan]:
        return [
            LabeledSpan(TimeRange(0.0, 5.0), SpanLabel.CORE, "s1", None),
            LabeledSpan(TimeRange(5.0, 10.0), SpanLabel.ANECDOTE, None, "конференционная байка"),
        ]


@dataclass
class FakeClaimExtraction:
    def extract_claims(self, core_text_with_timestamps: str, language: str):
        return [ExtractedClaim("Чёрные дыры испаряются.", TimeRange(0.0, 5.0))]


@dataclass
class FakeClaimVerification:
    def _outcome(self) -> VerificationOutcome:
        return VerificationOutcome(
            verdict=Verdict.CONFIRMED,
            sources=("https://doi.org/10.1038/248030a0",),
            annotation=None,
            evidence_urls=("https://doi.org/10.1038/248030a0",),
        )

    def verify_batch(self, claim_texts, language: str) -> list[VerificationOutcome]:
        return [self._outcome() for _ in claim_texts]


@dataclass
class FakeSectionComposition:
    calls: int = 0
    illustration_request: IllustrationRequest | None = None

    def compose_section(
        self,
        outline,
        target: SectionPlanEntry,
        parent,
        core_text: str,
        claims,
        frames,
        language: str,
        lecture_title: str,
        intro_only: bool,
    ) -> SectionComposition:
        self.calls += 1
        blocks: tuple[NoteBlock, ...] = (
            NoteBlock(kind=BlockKind.PROSE, text="Хокинг показал, что **чёрные дыры** излучают."),
            NoteBlock(
                kind=BlockKind.DEFINITION,
                term="Излучение Хокинга",
                text="Квантовое испарение чёрной дыры у горизонта событий.",
            ),
            NoteBlock(kind=BlockKind.FACT, text="Малые дыры испаряются быстрее больших."),
        )
        for indexed in claims:
            blocks += (
                NoteBlock(
                    kind=BlockKind.FACTCHECK_NOTE,
                    text="Утверждение согласуется с литературой.",
                    claim_ref=indexed.global_index,
                ),
            )
        return SectionComposition(blocks=blocks, illustration_request=self.illustration_request)


@dataclass
class FakeExternalImages:
    def download(self, image_url: str, dest_dir: str) -> str | None:
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        stored = Path(dest_dir) / "commons.jpg"
        stored.write_bytes(b"\xff\xd8fake")
        return str(stored)


@dataclass
class FakeImageSearch:
    candidates: tuple[ImageCandidate, ...] = ()

    def search(self, query: str, limit: int):
        return list(self.candidates[:limit])


@dataclass
class FakeImageGeneration:
    def generate(self, prompt: str, dest_dir: str, file_stem: str) -> str | None:
        return None


@dataclass
class FakeVisionCheck:
    score: int = 90

    def assess(self, image_path: str, purpose: str) -> CandidateAssessment:
        return CandidateAssessment(score=self.score)


@dataclass
class FakeQuizGeneration:
    def generate(
        self, notes: Notes, config: QuizConfig, coverage_feedback: str | None = None
    ) -> Quiz:
        section_ids = [section.section_id for section in notes.sections]
        target = config.target_for(len(section_ids))
        questions = tuple(
            QuizQuestion(
                question_id=f"q{index}",
                type=QuestionType.MULTI_SELECT if index == 0 else QuestionType.SINGLE_CHOICE,
                prompt=f"Вопрос {index}?",
                section_id=section_ids[index % len(section_ids)],
                options=("а", "б", "в", "г"),
                correct_options=(0, 2) if index == 0 else (index % 4,),
            )
            for index in range(target - 1)
        ) + (
            QuizQuestion(
                question_id="q-open",
                type=QuestionType.OPEN,
                prompt="Объясните механизм излучения.",
                section_id=section_ids[-1],
                model_answer="Квантовые эффекты у горизонта событий.",
                rubric=Rubric(
                    max_points=3,
                    concepts=(
                        RubricConcept("Квантовые эффекты у горизонта", 2),
                        RubricConcept("Испарение массы", 1),
                    ),
                ),
            ),
        )
        return Quiz(questions=questions)


@dataclass
class FakePdfCompiler:
    calls: int = 0

    def compile(self, markup_path: Path, root_dir: Path, font_dirs: list[Path]) -> bytes:
        self.calls += 1
        return b"%PDF-1.7 fake\n%%EOF"


@dataclass
class FakePorts:
    media_tools: FakeMediaTools = field(default_factory=FakeMediaTools)
    transcription: FakeTranscription = field(default_factory=FakeTranscription)
    frame_capture: FakeFrameCapture = field(default_factory=FakeFrameCapture)
    ocr: FakeOcr = field(default_factory=FakeOcr)
    layout_detection: FakeLayoutDetection = field(default_factory=FakeLayoutDetection)
    segmentation_llm: FakeSegmentationLlm = field(default_factory=FakeSegmentationLlm)
    claim_extraction: FakeClaimExtraction = field(default_factory=FakeClaimExtraction)
    claim_verification: FakeClaimVerification = field(default_factory=FakeClaimVerification)
    notes_composition: FakeSectionComposition = field(default_factory=FakeSectionComposition)
    external_images: FakeExternalImages = field(default_factory=FakeExternalImages)
    image_search: FakeImageSearch = field(default_factory=FakeImageSearch)
    image_generation: FakeImageGeneration = field(default_factory=FakeImageGeneration)
    vision_check: FakeVisionCheck = field(default_factory=FakeVisionCheck)
    quiz_generation: FakeQuizGeneration = field(default_factory=FakeQuizGeneration)
    pdf_compiler: FakePdfCompiler = field(default_factory=FakePdfCompiler)

    def as_ports(self) -> PipelinePorts:
        return PipelinePorts(
            media_tools=self.media_tools,
            transcription=self.transcription,
            frame_capture=self.frame_capture,
            ocr=self.ocr,
            layout_detection=self.layout_detection,
            segmentation_llm=self.segmentation_llm,
            claim_extraction=self.claim_extraction,
            claim_verification=self.claim_verification,
            notes_composition=self.notes_composition,
            external_images=self.external_images,
            image_search=self.image_search,
            image_generation=self.image_generation,
            vision_check=self.vision_check,
            quiz_generation=self.quiz_generation,
            pdf_compiler=self.pdf_compiler,
        )
