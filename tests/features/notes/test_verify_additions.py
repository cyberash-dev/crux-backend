# @covers analysis:REQ-028
import logging
from collections.abc import Sequence

import pytest

from konspekt.features.factcheck.domain.claims import Verdict, VerificationOutcome
from konspekt.features.factcheck.ports.outbound.factcheck_llm import (
    ClaimVerificationPort,
)
from konspekt.features.factcheck.ports.outbound.search_credential_error import (
    SearchCredentialError,
)
from konspekt.features.factcheck.ports.outbound.search_credits_exhausted_error import (
    SearchCreditsExhaustedError,
)
from konspekt.features.notes.application.verify_additions import AdditionVerifier
from konspekt.features.notes.domain.audit import AdditionAction, VerifiedAddition
from konspekt.features.notes.domain.notes import (
    BlockKind,
    BlockOrigin,
    NoteBlock,
    NoteSection,
    Notes,
)
from konspekt.shared.budget import BudgetExceededError
from konspekt.shared.timecode import TimeRange


class FakeVerification:
    def __init__(self, outcomes_by_claim_text: dict[str, VerificationOutcome]) -> None:
        self._outcomes_by_claim_text = outcomes_by_claim_text
        self.batches: list[list[str]] = []
        self.languages: list[str] = []

    def verify_batch(
        self, claim_texts: Sequence[str], language: str
    ) -> list[VerificationOutcome]:
        self.batches.append(list(claim_texts))
        self.languages.append(language)
        return [self._outcomes_by_claim_text[text] for text in claim_texts]


class FailingVerification:
    def verify_batch(
        self, claim_texts: Sequence[str], language: str
    ) -> list[VerificationOutcome]:
        raise ConnectionError("verification backend unavailable")


class BudgetExhaustedVerification:
    def verify_batch(
        self, claim_texts: Sequence[str], language: str
    ) -> list[VerificationOutcome]:
        raise BudgetExceededError(spent_usd=9.9, max_usd=10.0, attempted_usd=0.5)


def notes_with_blocks(*blocks: NoteBlock) -> Notes:
    return Notes(
        title="Анатомия",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Кости",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=blocks,
            ),
        ),
    )


def a_fact(text: str, origin: BlockOrigin | None) -> NoteBlock:
    return NoteBlock(kind=BlockKind.FACT, text=text, origin=origin)


def a_definition(term: str, text: str, origin: BlockOrigin | None) -> NoteBlock:
    return NoteBlock(kind=BlockKind.DEFINITION, term=term, text=text, origin=origin)


def a_confirmed_outcome() -> VerificationOutcome:
    return VerificationOutcome(
        verdict=Verdict.CONFIRMED,
        sources=("https://doi.org/10.1000/ok",),
        evidence_urls=("https://doi.org/10.1000/ok",),
        annotation=None,
    )


def a_disputed_outcome() -> VerificationOutcome:
    return VerificationOutcome(
        verdict=Verdict.DISPUTED,
        sources=("https://doi.org/10.1000/contra",),
        evidence_urls=("https://doi.org/10.1000/contra",),
        annotation="Источники утверждают обратное.",
    )


def a_disputed_outcome_citing_outside_the_evidence() -> VerificationOutcome:
    return VerificationOutcome(
        verdict=Verdict.DISPUTED,
        sources=("https://doi.org/10.1000/contra",),
        evidence_urls=("https://doi.org/10.1000/other",),
        annotation="Источники утверждают обратное.",
    )


def an_unverified_outcome() -> VerificationOutcome:
    return VerificationOutcome(verdict=Verdict.UNVERIFIED, sources=(), annotation=None)


def a_verifier(verification: ClaimVerificationPort, **kwargs: int) -> AdditionVerifier:
    return AdditionVerifier(verification=verification, **kwargs)


def test_model_added_fact_confirmed_is_kept() -> None:
    notes = notes_with_blocks(a_fact("Факт про кость.", BlockOrigin.MODEL_ADDED))
    verification = FakeVerification({"Факт про кость.": a_confirmed_outcome()})

    verified_notes, additions = a_verifier(verification).verify(notes)

    assert [block.text for block in verified_notes.sections[0].blocks] == [
        "Факт про кость."
    ]
    assert additions == (
        VerifiedAddition(
            text="Факт про кость.",
            origin=BlockOrigin.MODEL_ADDED,
            kind=BlockKind.FACT,
            verdict=Verdict.CONFIRMED,
            sources=("https://doi.org/10.1000/ok",),
            annotation=None,
            action=AdditionAction.KEPT,
        ),
    )


@pytest.mark.parametrize(
    "outcome",
    [
        VerificationOutcome(verdict=Verdict.UNVERIFIED, sources=(), annotation=None),
        VerificationOutcome(
            verdict=Verdict.DISPUTED,
            sources=("https://doi.org/10.1000/contra",),
            evidence_urls=("https://doi.org/10.1000/contra",),
            annotation="Источники утверждают обратное.",
        ),
        VerificationOutcome(
            verdict=Verdict.MIXED,
            sources=("https://doi.org/10.1000/mixed",),
            evidence_urls=("https://doi.org/10.1000/mixed",),
            annotation="Верно только в узком смысле.",
        ),
    ],
    ids=["unverified", "disputed", "mixed"],
)
def test_model_added_fact_without_confirmation_is_dropped(
    outcome: VerificationOutcome,
) -> None:
    notes = notes_with_blocks(
        a_fact("Сомнительный факт.", BlockOrigin.MODEL_ADDED),
        NoteBlock(kind=BlockKind.PROSE, text="Абзац."),
    )
    verification = FakeVerification({"Сомнительный факт.": outcome})

    verified_notes, additions = a_verifier(verification).verify(notes)

    assert [block.kind for block in verified_notes.sections[0].blocks] == [
        BlockKind.PROSE
    ]
    assert additions[0].action is AdditionAction.DROPPED


def test_model_added_definition_disputed_is_dropped() -> None:
    notes = notes_with_blocks(
        a_definition("Диафиз", "Неверная формулировка.", BlockOrigin.MODEL_ADDED)
    )
    verification = FakeVerification(
        {"Диафиз — Неверная формулировка.": a_disputed_outcome()}
    )

    verified_notes, additions = a_verifier(verification).verify(notes)

    assert verified_notes.sections[0].blocks == ()
    assert additions[0].action is AdditionAction.DROPPED
    assert additions[0].kind is BlockKind.DEFINITION


@pytest.mark.parametrize(
    "outcome",
    [
        VerificationOutcome(verdict=Verdict.UNVERIFIED, sources=(), annotation=None),
        VerificationOutcome(
            verdict=Verdict.CONFIRMED,
            sources=("https://doi.org/10.1000/ok",),
            evidence_urls=("https://doi.org/10.1000/ok",),
            annotation=None,
        ),
        VerificationOutcome(
            verdict=Verdict.MIXED,
            sources=("https://doi.org/10.1000/mixed",),
            evidence_urls=("https://doi.org/10.1000/mixed",),
            annotation="Верно только в узком смысле.",
        ),
    ],
    ids=["unverified", "confirmed", "mixed"],
)
def test_model_added_definition_without_dispute_is_kept(
    outcome: VerificationOutcome,
) -> None:
    notes = notes_with_blocks(
        a_definition("Диафиз", "Средняя часть кости.", BlockOrigin.MODEL_ADDED)
    )
    verification = FakeVerification({"Диафиз — Средняя часть кости.": outcome})

    verified_notes, additions = a_verifier(verification).verify(notes)

    assert verified_notes.sections[0].blocks[0].term == "Диафиз"
    assert additions[0].action is AdditionAction.KEPT


def test_lecture_fact_disputed_is_kept_with_warning_appended_to_text() -> None:
    notes = notes_with_blocks(a_fact("Спорный факт лектора.", BlockOrigin.LECTURE))
    verification = FakeVerification({"Спорный факт лектора.": a_disputed_outcome()})

    verified_notes, additions = a_verifier(verification).verify(notes)

    block = verified_notes.sections[0].blocks[0]
    assert block.text == (
        "Спорный факт лектора. "
        "(Источники утверждают обратное. — https://doi.org/10.1000/contra)"
    )
    assert additions[0].action is AdditionAction.KEPT_WITH_WARNING
    assert additions[0].verdict is Verdict.DISPUTED


def test_none_origin_is_treated_as_lecture() -> None:
    notes = notes_with_blocks(a_fact("Факт без происхождения.", None))
    verification = FakeVerification(
        {"Факт без происхождения.": a_disputed_outcome()}
    )

    verified_notes, additions = a_verifier(verification).verify(notes)

    assert len(verified_notes.sections[0].blocks) == 1
    assert additions[0].origin is BlockOrigin.LECTURE
    assert additions[0].action is AdditionAction.KEPT_WITH_WARNING


def test_lecture_fact_mixed_is_kept_without_warning() -> None:
    notes = notes_with_blocks(a_fact("Смешанный факт.", BlockOrigin.LECTURE))
    verification = FakeVerification(
        {
            "Смешанный факт.": VerificationOutcome(
                verdict=Verdict.MIXED,
                sources=("https://doi.org/10.1000/mixed",),
                evidence_urls=("https://doi.org/10.1000/mixed",),
                annotation="Верно только в узком смысле.",
            )
        }
    )

    verified_notes, additions = a_verifier(verification).verify(notes)

    assert verified_notes.sections[0].blocks[0].text == "Смешанный факт."
    assert additions[0].action is AdditionAction.KEPT


def test_only_fact_and_definition_blocks_are_verified() -> None:
    notes = notes_with_blocks(
        NoteBlock(kind=BlockKind.PROSE, text="Абзац."),
        a_fact("Факт.", BlockOrigin.LECTURE),
        NoteBlock(
            kind=BlockKind.FIGURE,
            image_path="frames/frame_30.png",
            source_ref="video 00:00:30",
        ),
        a_definition("Диафиз", "Средняя часть кости.", BlockOrigin.LECTURE),
    )
    verification = FakeVerification(
        {
            "Факт.": a_confirmed_outcome(),
            "Диафиз — Средняя часть кости.": a_confirmed_outcome(),
        }
    )

    _, additions = a_verifier(verification).verify(notes)

    assert sorted(text for batch in verification.batches for text in batch) == [
        "Диафиз — Средняя часть кости.",
        "Факт.",
    ]
    assert len(additions) == 2


def test_blocks_across_subsections_are_verified_in_tree_order() -> None:
    notes = Notes(
        title="Анатомия",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Кости",
                source_spans=(TimeRange(0.0, 60.0),),
                blocks=(a_fact("Факт родителя.", BlockOrigin.LECTURE),),
                subsections=(
                    NoteSection(
                        section_id="s1.1",
                        title="Диафиз",
                        source_spans=(TimeRange(0.0, 30.0),),
                        blocks=(a_fact("Факт подраздела.", BlockOrigin.LECTURE),),
                    ),
                ),
            ),
            NoteSection(
                section_id="s2",
                title="Мышцы",
                source_spans=(TimeRange(60.0, 120.0),),
                blocks=(a_fact("Факт второго раздела.", BlockOrigin.LECTURE),),
            ),
        ),
    )
    verification = FakeVerification(
        {
            "Факт родителя.": a_confirmed_outcome(),
            "Факт подраздела.": a_confirmed_outcome(),
            "Факт второго раздела.": a_confirmed_outcome(),
        }
    )

    _, additions = a_verifier(verification).verify(notes)

    assert [addition.text for addition in additions] == [
        "Факт родителя.",
        "Факт подраздела.",
        "Факт второго раздела.",
    ]


def test_language_of_the_notes_is_forwarded_to_the_port() -> None:
    notes = notes_with_blocks(a_fact("Факт.", BlockOrigin.LECTURE))
    verification = FakeVerification({"Факт.": a_confirmed_outcome()})

    a_verifier(verification).verify(notes)

    assert verification.languages == ["ru"]


def test_claims_are_verified_in_batches_of_batch_size() -> None:
    facts = [a_fact(f"Факт {index}.", BlockOrigin.LECTURE) for index in range(7)]
    notes = notes_with_blocks(*facts)
    verification = FakeVerification(
        {f"Факт {index}.": a_confirmed_outcome() for index in range(7)}
    )

    a_verifier(verification, batch_size=5).verify(notes)

    assert sorted(len(batch) for batch in verification.batches) == [2, 5]


def test_disputed_citing_outside_the_evidence_is_gated_to_unverified() -> None:
    notes = notes_with_blocks(
        a_fact("Факт лектора.", BlockOrigin.LECTURE),
        a_fact("Факт модели.", BlockOrigin.MODEL_ADDED),
    )
    verification = FakeVerification(
        {
            "Факт лектора.": a_disputed_outcome_citing_outside_the_evidence(),
            "Факт модели.": a_disputed_outcome_citing_outside_the_evidence(),
        }
    )

    verified_notes, additions = a_verifier(verification).verify(notes)

    assert [block.text for block in verified_notes.sections[0].blocks] == [
        "Факт лектора."
    ]
    assert [addition.verdict for addition in additions] == [
        Verdict.UNVERIFIED,
        Verdict.UNVERIFIED,
    ]
    assert [addition.action for addition in additions] == [
        AdditionAction.KEPT,
        AdditionAction.DROPPED,
    ]


def test_port_failure_degrades_outcomes_to_unverified() -> None:
    notes = notes_with_blocks(
        a_fact("Факт лектора.", BlockOrigin.LECTURE),
        a_fact("Факт модели.", BlockOrigin.MODEL_ADDED),
    )

    verified_notes, additions = a_verifier(FailingVerification()).verify(notes)

    assert [block.text for block in verified_notes.sections[0].blocks] == [
        "Факт лектора."
    ]
    assert [addition.verdict for addition in additions] == [
        Verdict.UNVERIFIED,
        Verdict.UNVERIFIED,
    ]
    assert [addition.action for addition in additions] == [
        AdditionAction.KEPT,
        AdditionAction.DROPPED,
    ]


def test_budget_exceeded_propagates() -> None:
    notes = notes_with_blocks(a_fact("Факт.", BlockOrigin.LECTURE))

    with pytest.raises(BudgetExceededError):
        a_verifier(BudgetExhaustedVerification()).verify(notes)


class RaisingVerification:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def verify_batch(
        self, claim_texts: list[str], language: str
    ) -> list[VerificationOutcome]:
        raise self._error


@pytest.mark.parametrize(
    "search_error",
    [
        SearchCredentialError("Exa rejected the API key (HTTP 401)"),
        SearchCreditsExhaustedError("Exa credits exhausted (HTTP 402)"),
    ],
    ids=["rejected key", "credits exhausted"],
)
def test_search_account_failure_propagates(search_error: Exception) -> None:
    # @covers analysis:EXT-014
    notes = notes_with_blocks(a_fact("Факт.", BlockOrigin.LECTURE))

    with pytest.raises(type(search_error), match="HTTP 40"):
        a_verifier(RaisingVerification(search_error)).verify(notes)


def test_notes_without_fact_or_definition_blocks_skip_the_port() -> None:
    notes = notes_with_blocks(NoteBlock(kind=BlockKind.PROSE, text="Абзац."))
    verification = FakeVerification({})

    verified_notes, additions = a_verifier(verification).verify(notes)

    assert verified_notes == notes
    assert additions == ()
    assert verification.batches == []


def test_dropped_block_is_logged_with_structured_context() -> None:
    notes = notes_with_blocks(a_fact("Сомнительный факт.", BlockOrigin.MODEL_ADDED))
    verification = FakeVerification({"Сомнительный факт.": an_unverified_outcome()})
    logger = logging.getLogger("konspekt.features.notes.application.verify_additions")
    captured_records: list[logging.LogRecord] = []

    class RecordingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured_records.append(record)

    handler = RecordingHandler()
    logger.addHandler(handler)
    try:
        a_verifier(verification).verify(notes)
    finally:
        logger.removeHandler(handler)

    assert len(captured_records) == 1
    assert captured_records[0].section_id == "s1"
    assert captured_records[0].verdict == "unverified"
