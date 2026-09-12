# @covers output:CON-032
# @covers output:DLT-037
from collections.abc import Sequence

from konspekt.features.compose.application.markdown_markup import (
    MarkdownBundle,
    render_markdown_bundle,
)
from konspekt.features.factcheck.domain.claims import CheckedClaim, Verdict
from konspekt.features.notes.domain.audit import AdditionAction, VerifiedAddition
from konspekt.features.notes.domain.notes import (
    BlockKind,
    BlockOrigin,
    ChartData,
    ChartKind,
    ChartSeries,
    DiagramData,
    DiagramEdge,
    DiagramKind,
    DiagramNode,
    NoteBlock,
    NoteSection,
    Notes,
    TableData,
)
from konspekt.features.segmentation.domain.segments import LabeledSpan, SpanLabel
from konspekt.shared.timecode import TimeRange
from tests.features.compose.metrics_fixture import a_metrics


def notes_with_blocks(blocks: tuple[NoteBlock, ...], language: str = "ru") -> Notes:
    return Notes(
        title="Скелет конечностей",
        language=language,
        sections=(
            NoteSection("s1", "Пояс", (TimeRange(0.0, 600.0),), blocks),
            NoteSection(
                "s2",
                "Свободная часть",
                (TimeRange(600.0, 1200.0),),
                (NoteBlock(kind=BlockKind.PROSE, text="Текст второго раздела."),),
                subsections=(
                    NoteSection(
                        "s2.1",
                        "Плечо",
                        (TimeRange(600.0, 900.0),),
                        (NoteBlock(kind=BlockKind.PROSE, text="Текст подраздела."),),
                    ),
                ),
            ),
        ),
    )


def a_bundle(
    blocks: tuple[NoteBlock, ...],
    language: str = "ru",
    claims: Sequence[CheckedClaim] | None = None,
    verified_additions: Sequence[VerifiedAddition] = (),
) -> MarkdownBundle:
    return render_markdown_bundle(
        notes_with_blocks(blocks, language),
        claims=claims
        if claims is not None
        else [
            CheckedClaim(
                "Кость растёт в длину за счёт эпифизарного хряща.",
                TimeRange(10.0, 20.0),
                Verdict.CONFIRMED,
                ("https://doi.org/10.1000/x",),
                None,
                claim_id="c_001",
            )
        ],
        cut_spans=[LabeledSpan(TimeRange(1200.0, 1260.0), SpanLabel.ANECDOTE, None, "байка")],
        video_file_name="lecture.mp4",
        generation_date="2026-08-22",
        metrics=a_metrics(),
        verified_additions=verified_additions,
    )


def test_readme_links_every_top_level_section_file_and_companions() -> None:
    bundle = a_bundle((NoteBlock(kind=BlockKind.PROSE, text="Проза."),))

    readme = bundle.files["README.md"]

    assert "# Скелет конечностей" in readme
    assert "[Пояс](sections/01-s1.md)" in readme
    assert "[Свободная часть](sections/02-s2.md)" in readme
    assert "[Плечо](sections/02-s2.md#s21)" in readme
    assert "(claims.md)" in readme and "(cut-log.md)" in readme
    assert "lecture.mp4" in readme and "2026-08-22" in readme


def test_section_file_carries_headings_time_ranges_and_subsections() -> None:
    bundle = a_bundle((NoteBlock(kind=BlockKind.PROSE, text="Проза."),))

    section_file = bundle.files["sections/02-s2.md"]

    assert section_file.startswith("# Свободная часть")
    assert "00:10:00 – 00:20:00" in section_file
    assert "## Плечо" in section_file
    assert "Текст подраздела." in section_file


def test_definition_fact_and_factcheck_render_as_labelled_blockquotes() -> None:
    bundle = a_bundle(
        (
            NoteBlock(kind=BlockKind.DEFINITION, term="Лопатка", text="Плоская кость."),
            NoteBlock(kind=BlockKind.FACT, text="Из 206 костей 126 в конечностях."),
            NoteBlock(
                kind=BlockKind.FACTCHECK_NOTE,
                text="Источник даёт 80, а не 82.",
                claim_ref=0,
                source_ref="https://doi.org/10.1000/x",
            ),
        )
    )

    section_file = bundle.files["sections/01-s1.md"]

    assert "> **Лопатка** — Плоская кость." in section_file
    assert "> **Интересный факт.** Из 206 костей 126 в конечностях." in section_file
    assert (
        "> **Проверка факта.** Источник даёт 80, а не 82. (https://doi.org/10.1000/x)"
        in section_file
    )


def test_english_notes_use_english_labels() -> None:
    bundle = a_bundle((NoteBlock(kind=BlockKind.FACT, text="Fact."),), language="en")

    assert "> **Interesting fact.** Fact." in bundle.files["sections/01-s1.md"]
    assert "## Contents" in bundle.files["README.md"]


def test_figure_renders_as_image_with_source_line_and_generated_label() -> None:
    bundle = a_bundle(
        (
            NoteBlock(
                kind=BlockKind.FIGURE,
                image_path="frames/frame_1000.jpg",
                caption="Лопатка сзади",
                source_ref="video 00:16:40",
            ),
            NoteBlock(
                kind=BlockKind.FIGURE,
                image_path="images/illustration_s1.png",
                caption="Ключица",
                source_ref="generated:codex",
            ),
        )
    )

    section_file = bundle.files["sections/01-s1.md"]

    assert "![Лопатка сзади](images/frame_1000.jpg)" in section_file
    assert "*Источник: video 00:16:40*" in section_file
    assert "*Источник: generated:codex · Иллюстрация сгенерирована ИИ*" in section_file
    assert bundle.image_paths == ("frames/frame_1000.jpg", "images/illustration_s1.png")


def test_table_renders_as_gfm_table() -> None:
    bundle = a_bundle(
        (
            NoteBlock(
                kind=BlockKind.TABLE,
                caption="Кости",
                table=TableData(("Кость", "Тип"), (("Лучевая", "трубчатая"),)),
            ),
        )
    )

    section_file = bundle.files["sections/01-s1.md"]

    assert "| Кость | Тип |\n| --- | --- |\n| Лучевая | трубчатая |" in section_file
    assert "*Кости*" in section_file


def test_diagrams_render_as_mermaid_with_quoted_labels_and_edge_labels() -> None:
    bundle = a_bundle(
        (
            NoteBlock(
                kind=BlockKind.DIAGRAM,
                caption="Классификация",
                diagram=DiagramData(
                    DiagramKind.HIERARCHY,
                    (DiagramNode("a", 'Кости "длинные"'), DiagramNode("b", "Трубчатые")),
                    (DiagramEdge("a", "b", "включают"),),
                ),
            ),
            NoteBlock(
                kind=BlockKind.DIAGRAM,
                caption="Процесс",
                diagram=DiagramData(
                    DiagramKind.FLOW,
                    (DiagramNode("x", "Хрящ"), DiagramNode("y", "Кость")),
                    (DiagramEdge("x", "y"),),
                ),
            ),
        )
    )

    section_file = bundle.files["sections/01-s1.md"]

    assert '```mermaid\ngraph TD\n    a["Кости #quot;длинные#quot;"]\n    b["Трубчатые"]\n    a -->|"включают"| b\n```' in section_file
    assert '```mermaid\ngraph LR\n    x["Хрящ"]\n    y["Кость"]\n    x --> y\n```' in section_file


def test_chart_renders_as_table_with_one_column_per_series() -> None:
    bundle = a_bundle(
        (
            NoteBlock(
                kind=BlockKind.CHART,
                caption="Рост",
                chart=ChartData(
                    ChartKind.LINE,
                    ("0", "5"),
                    (ChartSeries("Мальчики", (10.0, 25.5)), ChartSeries("Девочки", (10.0, 26.0))),
                    x_title="Возраст",
                    y_title="см",
                ),
            ),
        )
    )

    section_file = bundle.files["sections/01-s1.md"]

    assert "| Возраст | Мальчики | Девочки |\n| --- | --- | --- |\n| 0 | 10 | 10 |\n| 5 | 25.5 | 26 |" in section_file
    assert "line" in section_file and "см" in section_file


def test_claims_and_cut_log_files_are_tables() -> None:
    bundle = a_bundle((NoteBlock(kind=BlockKind.PROSE, text="Проза."),))

    assert "| 00:00:10 – 00:00:20 | confirmed |" in bundle.files["claims.md"]
    assert "https://doi.org/10.1000/x" in bundle.files["claims.md"]
    assert "| 00:20:00 – 00:21:00 | anecdote | байка |" in bundle.files["cut-log.md"]


def test_pipe_characters_in_cells_are_escaped() -> None:
    bundle = a_bundle(
        (
            NoteBlock(
                kind=BlockKind.TABLE,
                caption=None,
                table=TableData(("a|b",), (("1|2",),)),
            ),
        )
    )

    assert "| a\\|b |" in bundle.files["sections/01-s1.md"]
    assert "| 1\\|2 |" in bundle.files["sections/01-s1.md"]


# @covers output:DLT-034
def test_combined_document_holds_every_section_with_demoted_headings() -> None:
    bundle = a_bundle((NoteBlock(kind=BlockKind.PROSE, text="Проза."),))

    combined = bundle.combined

    assert combined.startswith("# Скелет конечностей")
    assert '## Пояс <a id="s1"></a>' in combined
    assert '## Свободная часть <a id="s2"></a>' in combined
    assert '### Плечо <a id="s21"></a>' in combined
    assert "Проза." in combined and "Текст подраздела." in combined
    assert "- [Пояс](#s1) `s1`" in combined and "  - [Плечо](#s21) `s2.1`" in combined
    assert "## Проверка фактов" in combined and "## Вырезанные фрагменты" in combined
    assert combined.index("## Проверка фактов") > combined.index("### Плечо")


# @covers output:DLT-034
def test_combined_document_links_images_under_the_bundle_images_dir() -> None:
    bundle = a_bundle(
        (
            NoteBlock(
                kind=BlockKind.FIGURE,
                image_path="frames/frame_1000.jpg",
                caption="Лопатка",
                source_ref="video 00:16:40",
            ),
        )
    )

    assert "![Лопатка](md/images/frame_1000.jpg)" in bundle.combined
    assert "![Лопатка](images/frame_1000.jpg)" in bundle.files["sections/01-s1.md"]


def a_prose_block() -> NoteBlock:
    return NoteBlock(kind=BlockKind.PROSE, text="Проза.")


def a_checked_claim(
    claim_id: str,
    verdict: Verdict,
    start_seconds: float,
    corrected_text: str | None = None,
) -> CheckedClaim:
    return CheckedClaim(
        f"Утверждение {claim_id}.",
        TimeRange(start_seconds, start_seconds + 10.0),
        verdict,
        ("https://doi.org/10.1000/x",),
        "комментарий" if verdict in (Verdict.DISPUTED, Verdict.MIXED) else None,
        claim_id=claim_id,
        corrected_text=corrected_text,
    )


def a_verified_addition() -> VerifiedAddition:
    return VerifiedAddition(
        text="Локтевая кость длиннее лучевой.",
        origin=BlockOrigin.MODEL_ADDED,
        kind=BlockKind.FACT,
        verdict=Verdict.CONFIRMED,
        sources=("https://doi.org/10.1000/y",),
        annotation=None,
        action=AdditionAction.KEPT,
    )


def test_readme_carries_metrics_block_after_header_list() -> None:
    bundle = a_bundle((a_prose_block(),))

    readme = bundle.files["README.md"]

    assert "- Длительность источника: 1:23:45" in readme
    assert "- Учтено в конспекте: 1:20:30" in readme
    assert "- Включено: 1:10:00" in readme
    assert "- Вырезано: 0:10:30" in readme
    assert "- Покрытие таймлайна: 96.1%" in readme
    assert "- Проверено утверждений: 5" in readme
    assert "- Вопросы для самопроверки: 8" in readme
    assert readme.index("lecture.mp4") < readme.index("Длительность источника")
    assert readme.index("Длительность источника") < readme.index("Конспект лекции")


def test_combined_document_carries_the_same_metrics_block() -> None:
    bundle = a_bundle((a_prose_block(),))

    combined = bundle.combined

    assert "- Длительность источника: 1:23:45" in combined
    assert "- Покрытие таймлайна: 96.1%" in combined
    assert "- Вопросы для самопроверки: 8" in combined


def test_metrics_block_uses_english_labels_for_english_notes() -> None:
    bundle = a_bundle((NoteBlock(kind=BlockKind.PROSE, text="Prose."),), language="en")

    readme = bundle.files["README.md"]

    assert "- Source duration: 1:23:45" in readme
    assert "- Timeline coverage: 96.1%" in readme


def test_claims_ledger_orders_disputed_and_mixed_before_confirmed() -> None:
    bundle = a_bundle(
        (a_prose_block(),),
        claims=[
            a_checked_claim("c_001", Verdict.CONFIRMED, 10.0),
            a_checked_claim("c_002", Verdict.DISPUTED, 300.0),
            a_checked_claim("c_003", Verdict.MIXED, 100.0),
        ],
    )

    ledger = bundle.files["claims.md"]

    assert ledger.index("c_003") < ledger.index("c_002")
    assert ledger.index("c_002") < ledger.index("c_001")


def test_claims_ledger_carries_id_verdict_correction_and_sources_columns() -> None:
    bundle = a_bundle(
        (a_prose_block(),),
        claims=[
            a_checked_claim(
                "c_001", Verdict.DISPUTED, 10.0, corrected_text="Исправленный текст."
            )
        ],
    )

    ledger = bundle.files["claims.md"]

    assert (
        "| ID | Утверждение | Время | Вердикт | Комментарий | Исправление | Источники |"
        in ledger
    )
    assert (
        "| c_001 | Утверждение c_001. | 00:00:10 – 00:00:20 | disputed | комментарий "
        "| Исправленный текст. | https://doi.org/10.1000/x |" in ledger
    )


def test_model_added_table_lists_verified_additions() -> None:
    bundle = a_bundle((a_prose_block(),), verified_additions=(a_verified_addition(),))

    ledger = bundle.files["claims.md"]

    assert "## Добавлено моделью" in ledger
    assert (
        "| Текст | Тип | Происхождение | Вердикт | Действие | Комментарий | Источники |"
        in ledger
    )
    assert (
        "| Локтевая кость длиннее лучевой. | fact | model_added | confirmed | kept "
        "|  | https://doi.org/10.1000/y |" in ledger
    )


def test_combined_document_carries_model_added_table() -> None:
    bundle = a_bundle((a_prose_block(),), verified_additions=(a_verified_addition(),))

    assert "Добавлено моделью" in bundle.combined
    assert "Локтевая кость длиннее лучевой." in bundle.combined


def test_model_added_section_is_omitted_when_no_additions() -> None:
    bundle = a_bundle((a_prose_block(),))

    assert "Добавлено моделью" not in bundle.files["claims.md"]
    assert "Добавлено моделью" not in bundle.combined
