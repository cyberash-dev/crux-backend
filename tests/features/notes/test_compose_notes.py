# @covers analysis:REQ-024
# @covers analysis:EXT-010
# @covers analysis:DLT-023
# @covers analysis:CON-022
# @covers analysis:DLT-025
# @covers analysis:DLT-026
# @covers analysis:REQ-027
# @covers analysis:ASM-022
# @covers analysis:DLT-028
# @covers analysis:DLT-031
# @covers analysis:REQ-028
import logging
import time
from pathlib import Path

import pytest

from konspekt.features.factcheck.domain.claims import (
    CheckedClaim,
    Verdict,
    VerificationOutcome,
)
from konspekt.features.notes.application.artifact import NotesArtifactError
from konspekt.features.notes.application.compose_notes import (
    ComposedNotes,
    NotesCompositionError,
    NotesValidationError,
    SectionedNotesComposer,
)
from konspekt.features.notes.application.resolve_illustrations import IllustrationResolver
from konspekt.features.notes.application.verify_additions import AdditionVerifier
from konspekt.features.notes.domain.audit import AdditionAction
from konspekt.features.notes.domain.illustration import (
    CandidateAssessment,
    IllustrationRequest,
)
from konspekt.features.notes.domain.notes import (
    BlockKind,
    BlockOrigin,
    FigureProvenance,
    NoteBlock,
)
from konspekt.features.notes.ports.outbound.notes_llm import (
    ImageCandidate,
    IndexedClaim,
    SectionComposition,
)
from konspekt.features.segmentation.domain.segments import (
    LabeledSpan,
    SectionPlanEntry,
    SegmentationResult,
    SpanLabel,
)
from konspekt.features.transcription.domain.transcript import Transcript, TranscriptSegment
from konspekt.features.visual.domain.frame import Frame
from konspekt.shared.budget import BudgetExceededError
from konspekt.shared.timecode import TimeRange


class FakeSectionComposition:
    def __init__(
        self,
        blocks_by_section: dict[str, tuple[NoteBlock, ...]] | None = None,
        failures_by_section: dict[str, list[Exception]] | None = None,
        delay_seconds_by_section: dict[str, float] | None = None,
        requests_by_section: dict[str, IllustrationRequest] | None = None,
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self._blocks_by_section = blocks_by_section or {}
        self._failures_by_section = failures_by_section or {}
        self._delay_seconds_by_section = delay_seconds_by_section or {}
        self._requests_by_section = requests_by_section or {}

    def compose_section(
        self,
        outline: tuple[SectionPlanEntry, ...],
        target: SectionPlanEntry,
        parent: SectionPlanEntry | None,
        core_text: str,
        claims: list[IndexedClaim],
        frames: list[Frame],
        language: str,
        lecture_title: str,
        intro_only: bool,
    ) -> SectionComposition:
        self.calls.append(
            {
                "outline": outline,
                "target_id": target.section_id,
                "parent_id": parent.section_id if parent is not None else None,
                "core_text": core_text,
                "claims": list(claims),
                "frames": list(frames),
                "language": language,
                "lecture_title": lecture_title,
                "intro_only": intro_only,
            }
        )
        time.sleep(self._delay_seconds_by_section.get(target.section_id, 0.0))
        pending_failures = self._failures_by_section.get(target.section_id)
        if pending_failures:
            raise pending_failures.pop(0)
        return SectionComposition(
            blocks=self._blocks_for(target.section_id, intro_only),
            illustration_request=self._requests_by_section.get(target.section_id),
        )

    def _blocks_for(self, section_id: str, intro_only: bool) -> tuple[NoteBlock, ...]:
        if section_id in self._blocks_by_section:
            return self._blocks_by_section[section_id]
        prefix = "Вступление" if intro_only else "Текст"
        return (NoteBlock(kind=BlockKind.PROSE, text=f"{prefix} {section_id}."),)


class StubImages:
    def __init__(self, stored_path_by_url: dict[str, str]) -> None:
        self._stored_path_by_url = stored_path_by_url

    def download(self, image_url: str, dest_dir: str) -> str | None:
        return self._stored_path_by_url.get(image_url)


def a_transcript() -> Transcript:
    return Transcript(
        language="ru",
        segments=(
            TranscriptSegment(TimeRange(0.0, 60.0), "Энергия сохраняется.", None),
            TranscriptSegment(TimeRange(60.0, 120.0), "Работа и теплота.", None),
            TranscriptSegment(TimeRange(120.0, 180.0), "Энтропия не убывает.", None),
        ),
    )


def a_nested_segmentation() -> SegmentationResult:
    return SegmentationResult(
        lecture_title="Введение в термодинамику",
        sections_plan=(
            SectionPlanEntry(
                "s1",
                "Первое начало",
                TimeRange(0.0, 120.0),
                subsections=(
                    SectionPlanEntry("s1.1", "Энергия", TimeRange(0.0, 60.0)),
                    SectionPlanEntry("s1.2", "Работа и теплота", TimeRange(60.0, 120.0)),
                ),
            ),
            SectionPlanEntry("s2", "Второе начало", TimeRange(120.0, 180.0)),
        ),
        spans=(LabeledSpan(TimeRange(0.0, 180.0), SpanLabel.CORE, "s1", None),),
    )


def a_flat_segmentation() -> SegmentationResult:
    return SegmentationResult(
        lecture_title="Введение в термодинамику",
        sections_plan=(SectionPlanEntry("s1", "Первое начало", TimeRange(0.0, 60.0)),),
        spans=(LabeledSpan(TimeRange(0.0, 60.0), SpanLabel.CORE, "s1", None),),
    )


def a_claim(span: TimeRange) -> CheckedClaim:
    return CheckedClaim(
        claim_text="КПД не превышает предел Карно",
        span=span,
        verdict=Verdict.DISPUTED,
        sources=("https://example.com/carnot",),
        annotation="Источники расходятся.",
    )


def a_frame(timestamp_seconds: float) -> Frame:
    return Frame(
        timestamp_seconds=timestamp_seconds,
        image_path=Path(f"frames/frame_{int(timestamp_seconds)}.png"),
        dhash="0" * 16,
        ocr_text=None,
    )


def a_composer(
    port: FakeSectionComposition,
    images: StubImages | None = None,
    max_workers: int = 4,
    illustration_resolver: IllustrationResolver | None = None,
    addition_verifier: AdditionVerifier | None = None,
) -> SectionedNotesComposer:
    return SectionedNotesComposer(
        section_port=port,
        external_images=images if images is not None else StubImages({}),
        images_dir="images",
        max_workers=max_workers,
        illustration_resolver=illustration_resolver,
        addition_verifier=addition_verifier,
    )


def calls_for(port: FakeSectionComposition, section_id: str) -> list[dict[str, object]]:
    return [call for call in port.calls if call["target_id"] == section_id]


def test_assembly_mirrors_the_plan() -> None:
    port = FakeSectionComposition()

    notes = a_composer(port).compose(a_transcript(), a_nested_segmentation(), [], []).notes

    assert notes.title == "Введение в термодинамику"
    assert notes.language == "ru"
    assert [section.section_id for section in notes.sections] == ["s1", "s2"]
    parent = notes.sections[0]
    assert parent.title == "Первое начало"
    assert parent.source_spans == (TimeRange(0.0, 120.0),)
    assert parent.blocks[0].text == "Вступление s1."
    assert [sub.section_id for sub in parent.subsections] == ["s1.1", "s1.2"]
    assert parent.subsections[0].blocks[0].text == "Текст s1.1."
    assert notes.sections[1].blocks[0].text == "Текст s2."


def test_parent_gets_intro_only_and_subsections_get_parent() -> None:
    port = FakeSectionComposition()

    a_composer(port).compose(a_transcript(), a_nested_segmentation(), [], [])

    assert calls_for(port, "s1")[0]["intro_only"] is True
    assert calls_for(port, "s1")[0]["parent_id"] is None
    assert calls_for(port, "s1.1")[0]["intro_only"] is False
    assert calls_for(port, "s1.1")[0]["parent_id"] == "s1"
    assert calls_for(port, "s2")[0]["intro_only"] is False
    assert calls_for(port, "s2")[0]["parent_id"] is None


def test_flat_entry_gets_one_full_call() -> None:
    port = FakeSectionComposition()

    a_composer(port).compose(a_transcript(), a_flat_segmentation(), [], [])

    assert len(port.calls) == 1
    assert port.calls[0]["intro_only"] is False


def test_claims_are_filtered_by_range_and_keep_global_indices() -> None:
    port = FakeSectionComposition()
    claims = [
        a_claim(TimeRange(10.0, 20.0)),
        a_claim(TimeRange(70.0, 80.0)),
        a_claim(TimeRange(130.0, 140.0)),
    ]

    a_composer(port).compose(a_transcript(), a_nested_segmentation(), claims, [])

    s2_claims = calls_for(port, "s2")[0]["claims"]
    assert s2_claims == [IndexedClaim(2, claims[2])]
    s11_claims = calls_for(port, "s1.1")[0]["claims"]
    assert s11_claims == [IndexedClaim(0, claims[0])]


def test_frames_are_filtered_by_range() -> None:
    port = FakeSectionComposition()
    frames = [a_frame(30.0), a_frame(150.0)]

    a_composer(port).compose(a_transcript(), a_nested_segmentation(), [], frames)

    assert calls_for(port, "s1.1")[0]["frames"] == [frames[0]]
    assert calls_for(port, "s1.2")[0]["frames"] == []
    assert calls_for(port, "s2")[0]["frames"] == [frames[1]]


def test_core_text_and_context_are_passed() -> None:
    port = FakeSectionComposition()

    a_composer(port).compose(a_transcript(), a_nested_segmentation(), [], [])

    s2_call = calls_for(port, "s2")[0]
    assert "Энтропия не убывает." in s2_call["core_text"]
    assert "Энергия сохраняется." not in s2_call["core_text"]
    assert s2_call["language"] == "ru"
    assert s2_call["lecture_title"] == "Введение в термодинамику"
    assert s2_call["outline"] == a_nested_segmentation().sections_plan


def test_parallel_composition_keeps_plan_order() -> None:
    port = FakeSectionComposition(delay_seconds_by_section={"s1": 0.05})

    notes = a_composer(port, max_workers=4).compose(
        a_transcript(), a_nested_segmentation(), [], []
    ).notes

    assert [section.section_id for section in notes.sections] == ["s1", "s2"]
    assert notes.sections[0].blocks[0].text == "Вступление s1."


def test_failed_section_is_retried_once_and_others_run_once() -> None:
    port = FakeSectionComposition(failures_by_section={"s2": [RuntimeError("boom")]})

    notes = a_composer(port).compose(a_transcript(), a_nested_segmentation(), [], []).notes

    assert len(calls_for(port, "s2")) == 2
    assert len(calls_for(port, "s1.1")) == 1
    assert notes.sections[1].blocks[0].text == "Текст s2."


def test_section_failing_twice_raises_typed_error_with_its_id() -> None:
    port = FakeSectionComposition(
        failures_by_section={"s2": [RuntimeError("boom"), RuntimeError("boom")]}
    )

    with pytest.raises(NotesCompositionError, match="s2"):
        a_composer(port).compose(a_transcript(), a_nested_segmentation(), [], [])


def test_budget_exceeded_propagates_without_retry() -> None:
    port = FakeSectionComposition(
        failures_by_section={"s2": [BudgetExceededError(1.0, 1.0, 0.5)]}
    )

    with pytest.raises(BudgetExceededError):
        a_composer(port).compose(a_transcript(), a_nested_segmentation(), [], [])

    assert len(calls_for(port, "s2")) == 1


def a_gapped_segmentation() -> SegmentationResult:
    return SegmentationResult(
        lecture_title="Введение в термодинамику",
        sections_plan=(
            SectionPlanEntry(
                "s1",
                "Первое начало",
                TimeRange(0.0, 120.0),
                subsections=(
                    SectionPlanEntry("s1.1", "Энергия", TimeRange(30.0, 60.0)),
                    SectionPlanEntry("s1.2", "Работа", TimeRange(60.0, 100.0)),
                ),
            ),
            SectionPlanEntry("s2", "Второе начало", TimeRange(120.0, 180.0)),
        ),
        spans=(LabeledSpan(TimeRange(0.0, 180.0), SpanLabel.CORE, "s1", None),),
    )


def a_gapped_transcript() -> Transcript:
    return Transcript(
        language="ru",
        segments=(
            TranscriptSegment(TimeRange(0.0, 20.0), "Собственный текст родителя.", None),
            TranscriptSegment(TimeRange(40.0, 50.0), "Текст энергии.", None),
            TranscriptSegment(TimeRange(102.0, 115.0), "Хвост родителя.", None),
            TranscriptSegment(TimeRange(130.0, 140.0), "Энтропия не убывает.", None),
        ),
    )


def test_intro_core_text_excludes_subsection_ranges() -> None:
    port = FakeSectionComposition()

    a_composer(port).compose(a_gapped_transcript(), a_gapped_segmentation(), [], [])

    intro_core_text = calls_for(port, "s1")[0]["core_text"]
    assert "Собственный текст родителя." in intro_core_text
    assert "Хвост родителя." in intro_core_text
    assert "Текст энергии." not in intro_core_text


def test_claim_inside_subsection_goes_only_to_that_subsection() -> None:
    port = FakeSectionComposition()
    claims = [a_claim(TimeRange(40.0, 50.0))]

    a_composer(port).compose(a_gapped_transcript(), a_gapped_segmentation(), claims, [])

    assert calls_for(port, "s1.1")[0]["claims"] == [IndexedClaim(0, claims[0])]
    assert calls_for(port, "s1")[0]["claims"] == []
    assert calls_for(port, "s1.2")[0]["claims"] == []


def test_claim_in_parent_own_zone_goes_to_the_parent() -> None:
    port = FakeSectionComposition()
    claims = [a_claim(TimeRange(5.0, 15.0))]

    a_composer(port).compose(a_gapped_transcript(), a_gapped_segmentation(), claims, [])

    assert calls_for(port, "s1")[0]["claims"] == [IndexedClaim(0, claims[0])]
    assert calls_for(port, "s1.1")[0]["claims"] == []


def test_frames_are_assigned_exclusively_by_timestamp() -> None:
    port = FakeSectionComposition()
    frames = [a_frame(45.0), a_frame(10.0)]

    a_composer(port).compose(a_gapped_transcript(), a_gapped_segmentation(), [], frames)

    assert calls_for(port, "s1.1")[0]["frames"] == [frames[0]]
    assert calls_for(port, "s1")[0]["frames"] == [frames[1]]
    assert calls_for(port, "s1.2")[0]["frames"] == []


def a_definition(term: str) -> NoteBlock:
    return NoteBlock(
        kind=BlockKind.DEFINITION,
        term=term,
        text="Плоскость, делящая тело на левую и правую части.",
    )


def a_two_section_flat_segmentation() -> SegmentationResult:
    return SegmentationResult(
        lecture_title="Введение в термодинамику",
        sections_plan=(
            SectionPlanEntry("s1", "Первое начало", TimeRange(0.0, 60.0)),
            SectionPlanEntry("s2", "Второе начало", TimeRange(60.0, 120.0)),
        ),
        spans=(LabeledSpan(TimeRange(0.0, 120.0), SpanLabel.CORE, "s1", None),),
    )


def test_duplicate_definition_in_later_section_is_dropped_with_warning() -> None:
    port = FakeSectionComposition(
        blocks_by_section={
            "s1": (a_definition("Сагиттальная плоскость"),),
            "s2": (
                NoteBlock(kind=BlockKind.PROSE, text="Энтропия не убывает."),
                a_definition(" сагиттальная  ПЛОСКОСТЬ "),
            ),
        }
    )
    logger = logging.getLogger("konspekt.features.notes.application.compose_notes")
    captured_records: list[logging.LogRecord] = []

    class RecordingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured_records.append(record)

    handler = RecordingHandler()
    logger.addHandler(handler)
    try:
        notes = a_composer(port).compose(
            a_transcript(), a_two_section_flat_segmentation(), [], []
        ).notes
    finally:
        logger.removeHandler(handler)

    assert notes.sections[0].blocks[0].kind is BlockKind.DEFINITION
    assert [block.kind for block in notes.sections[1].blocks] == [BlockKind.PROSE]
    assert len(captured_records) == 1
    assert captured_records[0].section_id == "s2"
    assert captured_records[0].term == " сагиттальная  ПЛОСКОСТЬ "


def test_distinct_definitions_are_kept_unchanged() -> None:
    port = FakeSectionComposition(
        blocks_by_section={
            "s1": (a_definition("Сагиттальная плоскость"),),
            "s2": (a_definition("Фронтальная плоскость"),),
        }
    )

    notes = a_composer(port).compose(
        a_transcript(), a_two_section_flat_segmentation(), [], []
    ).notes

    assert notes.sections[0].blocks[0].term == "Сагиттальная плоскость"
    assert notes.sections[1].blocks[0].term == "Фронтальная плоскость"


def test_external_figure_is_downloaded_and_path_replaced() -> None:
    url = "https://example.com/diagram.png"
    port = FakeSectionComposition(
        blocks_by_section={
            "s1": (
                NoteBlock(kind=BlockKind.PROSE, text="Энергия сохраняется."),
                NoteBlock(kind=BlockKind.FIGURE, image_path=url, source_ref=url),
            )
        }
    )

    notes = a_composer(port, images=StubImages({url: "images/abc.png"})).compose(
        a_transcript(), a_flat_segmentation(), [], []
    ).notes

    figure = notes.sections[0].blocks[1]
    assert figure.image_path == "images/abc.png"
    assert figure.source_ref == url


def test_failed_download_drops_the_external_figure() -> None:
    url = "https://example.com/gone.png"
    port = FakeSectionComposition(
        blocks_by_section={
            "s1": (
                NoteBlock(kind=BlockKind.PROSE, text="Энергия сохраняется."),
                NoteBlock(kind=BlockKind.FIGURE, image_path=url, source_ref=url),
            )
        }
    )

    notes = a_composer(port).compose(a_transcript(), a_flat_segmentation(), [], []).notes

    assert [block.kind for block in notes.sections[0].blocks] == [BlockKind.PROSE]


def test_misplaced_frame_figure_is_dropped_and_logged() -> None:
    port = FakeSectionComposition(
        blocks_by_section={
            "s1": (
                NoteBlock(kind=BlockKind.PROSE, text="Энергия сохраняется."),
                NoteBlock(
                    kind=BlockKind.FIGURE,
                    image_path="frames/frame_300.png",
                    source_ref="video 00:05:00",
                ),
                NoteBlock(
                    kind=BlockKind.FIGURE,
                    image_path="frames/frame_30.png",
                    source_ref="video 00:00:30",
                ),
            )
        }
    )
    logger = logging.getLogger("konspekt.features.notes.application.compose_notes")
    captured_records: list[logging.LogRecord] = []

    class RecordingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured_records.append(record)

    handler = RecordingHandler()
    logger.addHandler(handler)
    try:
        notes = a_composer(port).compose(
            a_transcript(), a_flat_segmentation(), [], [a_frame(30.0)]
        ).notes
    finally:
        logger.removeHandler(handler)

    kinds = [block.kind for block in notes.sections[0].blocks]
    assert kinds == [BlockKind.PROSE, BlockKind.FIGURE]
    assert notes.sections[0].blocks[1].source_ref == "video 00:00:30"
    assert len(captured_records) == 1
    assert captured_records[0].section_id == "s1"
    assert captured_records[0].figure_source_ref == "video 00:05:00"


def test_non_https_external_figure_still_fails_validation() -> None:
    port = FakeSectionComposition(
        blocks_by_section={
            "s1": (
                NoteBlock(
                    kind=BlockKind.FIGURE,
                    image_path="http://example.com/x.png",
                    source_ref="http://example.com/x.png",
                    provenance=FigureProvenance.COMMONS,
                ),
            )
        }
    )

    with pytest.raises(NotesValidationError, match="http://example.com/x.png"):
        a_composer(port).compose(a_transcript(), a_flat_segmentation(), [], [])


def test_dangling_global_claim_ref_is_rejected() -> None:
    port = FakeSectionComposition(
        blocks_by_section={
            "s1": (
                NoteBlock(
                    kind=BlockKind.FACTCHECK_NOTE, text="Источники расходятся.", claim_ref=7
                ),
            )
        }
    )

    with pytest.raises(NotesArtifactError, match="claim_ref"):
        a_composer(port).compose(
            a_transcript(), a_flat_segmentation(), [a_claim(TimeRange(10.0, 20.0))], []
        )


def test_global_claim_ref_within_claims_list_is_accepted() -> None:
    port = FakeSectionComposition(
        blocks_by_section={
            "s1": (
                NoteBlock(
                    kind=BlockKind.FACTCHECK_NOTE, text="Источники расходятся.", claim_ref=2
                ),
            )
        }
    )
    claims = [
        a_claim(TimeRange(10.0, 20.0)),
        a_claim(TimeRange(30.0, 40.0)),
        a_claim(TimeRange(50.0, 55.0)),
    ]

    notes = a_composer(port).compose(a_transcript(), a_flat_segmentation(), claims, []).notes

    assert notes.sections[0].blocks[0].claim_ref == 2


COMMONS_FILE_PAGE_URL = "https://commons.wikimedia.org/wiki/File:Radius_ulna.jpg"
COMMONS_IMAGE_URL = "https://upload.wikimedia.org/radius_ulna.jpg"


class StubCommonsSearch:
    def search(self, query: str, limit: int) -> list[ImageCandidate]:
        return [ImageCandidate(file_page_url=COMMONS_FILE_PAGE_URL, image_url=COMMONS_IMAGE_URL)]


class StubGenerator:
    def generate(self, prompt: str, dest_dir: str, file_stem: str) -> str | None:
        return f"{dest_dir}/{file_stem}.png"


class StubVision:
    def __init__(self, is_confirming: bool) -> None:
        self._is_confirming = is_confirming

    def assess(self, image_path: str, purpose: str) -> CandidateAssessment:
        return CandidateAssessment(score=90 if self._is_confirming else 0)


def a_resolver(is_confirming: bool) -> IllustrationResolver:
    return IllustrationResolver(
        search=StubCommonsSearch(),
        downloader=StubImages({COMMONS_IMAGE_URL: "images/radius_ulna.jpg"}),
        generator=StubGenerator(),
        vision=StubVision(is_confirming),
        images_dir="images",
    )


def an_illustration_request(insert_index: int) -> IllustrationRequest:
    return IllustrationRequest(
        purpose="Лучевая и локтевая кости, вид спереди",
        search_query="radius ulna bones anterior view",
        generation_prompt="Educational illustration of the radius and ulna",
        insert_index=insert_index,
    )


def two_prose_blocks() -> tuple[NoteBlock, ...]:
    return (
        NoteBlock(kind=BlockKind.PROSE, text="Первый абзац."),
        NoteBlock(kind=BlockKind.PROSE, text="Второй абзац."),
    )


def test_resolved_illustration_is_inserted_at_requested_index() -> None:
    port = FakeSectionComposition(
        blocks_by_section={"s1": two_prose_blocks()},
        requests_by_section={"s1": an_illustration_request(insert_index=1)},
    )

    notes = a_composer(port, illustration_resolver=a_resolver(is_confirming=True)).compose(
        a_transcript(), a_flat_segmentation(), [], []
    ).notes

    blocks = notes.sections[0].blocks
    assert [block.kind for block in blocks] == [BlockKind.PROSE, BlockKind.FIGURE, BlockKind.PROSE]
    assert blocks[1].provenance is FigureProvenance.COMMONS
    assert blocks[1].source_ref == COMMONS_FILE_PAGE_URL
    assert blocks[1].image_path == "images/radius_ulna.jpg"
    assert blocks[1].caption == "Лучевая и локтевая кости, вид спереди"


def test_insert_index_beyond_blocks_appends_the_figure() -> None:
    port = FakeSectionComposition(
        blocks_by_section={"s1": two_prose_blocks()},
        requests_by_section={"s1": an_illustration_request(insert_index=9)},
    )

    notes = a_composer(port, illustration_resolver=a_resolver(is_confirming=True)).compose(
        a_transcript(), a_flat_segmentation(), [], []
    ).notes

    kinds = [block.kind for block in notes.sections[0].blocks]
    assert kinds == [BlockKind.PROSE, BlockKind.PROSE, BlockKind.FIGURE]


def test_unresolved_request_keeps_every_other_block() -> None:
    port = FakeSectionComposition(
        blocks_by_section={"s1": two_prose_blocks()},
        requests_by_section={"s1": an_illustration_request(insert_index=1)},
    )

    notes = a_composer(port, illustration_resolver=a_resolver(is_confirming=False)).compose(
        a_transcript(), a_flat_segmentation(), [], []
    ).notes

    assert notes.sections[0].blocks == two_prose_blocks()


def test_request_without_resolver_is_dropped_and_logged() -> None:
    port = FakeSectionComposition(
        blocks_by_section={"s1": two_prose_blocks()},
        requests_by_section={"s1": an_illustration_request(insert_index=1)},
    )
    logger = logging.getLogger("konspekt.features.notes.application.compose_notes")
    captured_records: list[logging.LogRecord] = []

    class RecordingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured_records.append(record)

    handler = RecordingHandler()
    logger.addHandler(handler)
    try:
        notes = a_composer(port).compose(a_transcript(), a_flat_segmentation(), [], []).notes
    finally:
        logger.removeHandler(handler)

    assert notes.sections[0].blocks == two_prose_blocks()
    assert len(captured_records) == 1
    assert captured_records[0].section_id == "s1"


class MappedVerification:
    def __init__(self, outcomes_by_claim_text: dict[str, VerificationOutcome]) -> None:
        self._outcomes_by_claim_text = outcomes_by_claim_text

    def verify_batch(
        self, claim_texts: list[str], language: str
    ) -> list[VerificationOutcome]:
        return [self._outcomes_by_claim_text[text] for text in claim_texts]


def test_compose_returns_composed_notes_with_empty_additions_without_verifier() -> None:
    port = FakeSectionComposition()

    composed = a_composer(port).compose(a_transcript(), a_flat_segmentation(), [], [])

    assert isinstance(composed, ComposedNotes)
    assert composed.verified_additions == ()
    assert composed.notes.title == "Введение в термодинамику"


def test_compose_verifies_additions_and_drops_unconfirmed_model_added_fact() -> None:
    port = FakeSectionComposition(
        blocks_by_section={
            "s1": (
                NoteBlock(kind=BlockKind.PROSE, text="Абзац."),
                NoteBlock(
                    kind=BlockKind.FACT,
                    text="Выдуманный факт.",
                    origin=BlockOrigin.MODEL_ADDED,
                ),
                NoteBlock(
                    kind=BlockKind.FACT,
                    text="Настоящий факт.",
                    origin=BlockOrigin.MODEL_ADDED,
                ),
            )
        }
    )
    verifier = AdditionVerifier(
        verification=MappedVerification(
            {
                "Выдуманный факт.": VerificationOutcome(
                    verdict=Verdict.UNVERIFIED, sources=(), annotation=None
                ),
                "Настоящий факт.": VerificationOutcome(
                    verdict=Verdict.CONFIRMED,
                    sources=("https://doi.org/10.1000/ok",),
                    evidence_urls=("https://doi.org/10.1000/ok",),
                    annotation=None,
                ),
            }
        ),
    )

    composed = a_composer(port, addition_verifier=verifier).compose(
        a_transcript(), a_flat_segmentation(), [], []
    )

    assert [block.text for block in composed.notes.sections[0].blocks] == [
        "Абзац.",
        "Настоящий факт.",
    ]
    assert [addition.action for addition in composed.verified_additions] == [
        AdditionAction.DROPPED,
        AdditionAction.KEPT,
    ]


def a_port_with_model_added_then_lecture_definition_of_one_term() -> FakeSectionComposition:
    return FakeSectionComposition(
        blocks_by_section={
            "s1": (
                NoteBlock(
                    kind=BlockKind.DEFINITION,
                    term="Диафиз",
                    text="Неверная формулировка.",
                    origin=BlockOrigin.MODEL_ADDED,
                ),
            ),
            "s2": (
                NoteBlock(
                    kind=BlockKind.DEFINITION,
                    term="Диафиз",
                    text="Средняя часть трубчатой кости.",
                    origin=BlockOrigin.LECTURE,
                ),
            ),
        }
    )


def a_verifier_disputing_the_model_added_definition() -> AdditionVerifier:
    return AdditionVerifier(
        verification=MappedVerification(
            {
                "Диафиз — Неверная формулировка.": VerificationOutcome(
                    verdict=Verdict.DISPUTED,
                    sources=("https://doi.org/10.1000/contra",),
                    evidence_urls=("https://doi.org/10.1000/contra",),
                    annotation="Источники дают другое определение.",
                ),
                "Диафиз — Средняя часть трубчатой кости.": VerificationOutcome(
                    verdict=Verdict.CONFIRMED,
                    sources=("https://doi.org/10.1000/ok",),
                    evidence_urls=("https://doi.org/10.1000/ok",),
                    annotation=None,
                ),
            }
        ),
    )


# @covers analysis:REQ-028
# @covers analysis:DLT-026
def test_lecture_definition_survives_when_earlier_same_term_model_added_one_is_dropped() -> None:
    port = a_port_with_model_added_then_lecture_definition_of_one_term()
    verifier = a_verifier_disputing_the_model_added_definition()

    composed = a_composer(port, addition_verifier=verifier).compose(
        a_transcript(), a_two_section_flat_segmentation(), [], []
    )

    assert [block.text for block in composed.notes.sections[1].blocks] == [
        "Средняя часть трубчатой кости."
    ]


# @covers analysis:REQ-028
def test_later_same_term_lecture_definition_is_audited_when_earlier_one_is_dropped() -> None:
    port = a_port_with_model_added_then_lecture_definition_of_one_term()
    verifier = a_verifier_disputing_the_model_added_definition()

    composed = a_composer(port, addition_verifier=verifier).compose(
        a_transcript(), a_two_section_flat_segmentation(), [], []
    )

    assert [
        (addition.origin, addition.action) for addition in composed.verified_additions
    ] == [
        (BlockOrigin.MODEL_ADDED, AdditionAction.DROPPED),
        (BlockOrigin.LECTURE, AdditionAction.KEPT),
    ]


def test_compose_strips_emphasis_from_non_prose_fields() -> None:
    port = FakeSectionComposition(
        blocks_by_section={
            "s1": (
                NoteBlock(
                    kind=BlockKind.DEFINITION,
                    term="**Энтропия**",
                    text="Мера **беспорядка** системы.",
                ),
            )
        }
    )

    composed = a_composer(port).compose(a_transcript(), a_flat_segmentation(), [], [])

    block = composed.notes.sections[0].blocks[0]
    assert block.term == "Энтропия"
    assert block.text == "Мера **беспорядка** системы."


def test_illustration_request_inside_subsection_is_resolved_for_that_subsection() -> None:
    port = FakeSectionComposition(
        requests_by_section={"s1.2": an_illustration_request(insert_index=0)}
    )

    notes = a_composer(port, illustration_resolver=a_resolver(is_confirming=True)).compose(
        a_transcript(), a_nested_segmentation(), [], []
    ).notes

    subsection = notes.sections[0].subsections[1]
    assert [block.kind for block in subsection.blocks] == [BlockKind.FIGURE, BlockKind.PROSE]
    assert [block.kind for block in notes.sections[0].blocks] == [BlockKind.PROSE]
    assert [block.kind for block in notes.sections[1].blocks] == [BlockKind.PROSE]
