# @covers output:CON-030
# @covers output:DLT-030
# @covers output:DLT-031
# @covers output:DLT-036
from dataclasses import replace

from konspekt.features.compose.application.metrics import LectureMetrics
from konspekt.features.compose.application.typst_markup import (
    MAX_FIGURE_HEIGHT,
    DEFINITION_FILL,
    FACT_FILL,
    FACTCHECK_FILL,
    render_markup,
)
from konspekt.features.notes.domain.notes import BlockKind, NoteBlock, NoteSection, Notes
from konspekt.shared.timecode import TimeRange
from tests.features.compose.metrics_fixture import a_metrics

RU_PROSE_PROBE = "Пример проверки конспекта № 1"
EN_PROSE_PROBE = "Sample notes probe"
FIGURE_SOURCE_REF = "video 00:00:42"
FACTCHECK_TEXT = "Утверждение подтверждено: https://example.org/source"


def bilingual_notes() -> Notes:
    return Notes(
        title="Проверочная лекция",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Введение",
                source_spans=(TimeRange(0.0, 90.0),),
                blocks=(
                    NoteBlock(kind=BlockKind.PROSE, text=RU_PROSE_PROBE),
                    NoteBlock(
                        kind=BlockKind.FIGURE,
                        image_path="figures/frame.png",
                        caption="Схема с доски",
                        source_ref=FIGURE_SOURCE_REF,
                    ),
                    NoteBlock(
                        kind=BlockKind.FACTCHECK_NOTE,
                        text=FACTCHECK_TEXT,
                        claim_ref=0,
                    ),
                    NoteBlock(
                        kind=BlockKind.DEFINITION,
                        term="Конспект",
                        text="Структурированная запись **лекции**",
                    ),
                    NoteBlock(
                        kind=BlockKind.FACT,
                        text="Первые конспекты появились в античности",
                    ),
                ),
            ),
            NoteSection(
                section_id="s2",
                title="English part",
                source_spans=(TimeRange(90.0, 5025.0),),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text=EN_PROSE_PROBE),),
            ),
        ),
    )


def nested_notes() -> Notes:
    return Notes(
        title="Лекция с подсекциями",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Введение",
                source_spans=(TimeRange(0.0, 90.0),),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text="Текст родительской главы"),),
                subsections=(
                    NoteSection(
                        section_id="s1-1",
                        title="Детали метода",
                        source_spans=(TimeRange(30.0, 75.0),),
                        blocks=(
                            NoteBlock(kind=BlockKind.PROSE, text="Текст подсекции"),
                        ),
                    ),
                ),
            ),
        ),
    )


def test_subsection_renders_as_level_two_heading_after_parent_blocks() -> None:
    notes = nested_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "== Детали метода" in markup
    assert markup.index("= Введение") < markup.index("Текст родительской главы")
    assert markup.index("Текст родительской главы") < markup.index("== Детали метода")
    assert markup.index("== Детали метода") < markup.index("Текст подсекции")


def test_subsection_carries_time_range_labels() -> None:
    notes = nested_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    subsection_chapter = markup[markup.index("== Детали метода") :]
    assert "00:00:30 – 00:01:15" in subsection_chapter


def test_preamble_styles_level_two_headings() -> None:
    notes = nested_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "heading.where(level: 2)" in markup


def test_outline_covers_both_heading_levels() -> None:
    notes = nested_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "depth: 2" in markup


def test_flat_notes_render_no_level_two_headings() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "\n== " not in markup


def test_markup_contains_every_prose_string() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert RU_PROSE_PROBE in markup
    assert EN_PROSE_PROBE in markup


def test_markup_contains_figure_attribution_line() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert FIGURE_SOURCE_REF in markup


def test_markup_contains_factcheck_annotation_text() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "Утверждение подтверждено" in markup


def test_title_page_carries_title_video_name_and_date() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "Проверочная лекция" in markup
    assert "lecture.mp4" in markup
    assert "2026-08-19" in markup


def test_markup_contains_outline() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "#outline(" in markup


def test_section_carries_time_range_labels() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "00:00:00" in markup
    assert "00:01:30" in markup
    assert "01:23:45" in markup


def test_english_notes_use_english_static_headings() -> None:
    notes = Notes(
        title="Probe lecture",
        language="en",
        sections=(
            NoteSection(
                section_id="s1",
                title="Intro",
                source_spans=(TimeRange(0.0, 10.0),),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text=EN_PROSE_PROBE),),
            ),
        ),
    )

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "Contents" in markup


def test_markup_carries_no_quiz_or_answer_key_chapters() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "Тест для самопроверки" not in markup
    assert "Ключ ответов" not in markup
    assert "Self-check quiz" not in markup
    assert "Answer key" not in markup


def test_definition_renders_as_callout_with_bold_term_header() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    definition_callout = markup[
        markup.index(f'fill: rgb("{DEFINITION_FILL}")') : markup.index(
            f'fill: rgb("{FACT_FILL}")'
        )
    ]
    assert '#text(weight: "bold"' in definition_callout
    assert "Конспект" in definition_callout
    assert "Структурированная запись" in definition_callout


def test_fact_callout_carries_russian_label_for_russian_notes() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    fact_callout = markup[markup.index(f'fill: rgb("{FACT_FILL}")') :]
    assert "Интересный факт" in fact_callout
    assert "Первые конспекты появились в античности" in fact_callout


def test_fact_callout_carries_english_label_for_english_notes() -> None:
    notes = Notes(
        title="Probe lecture",
        language="en",
        sections=(
            NoteSection(
                section_id="s1",
                title="Intro",
                source_spans=(TimeRange(0.0, 10.0),),
                blocks=(NoteBlock(kind=BlockKind.FACT, text="Dolphins sleep with one eye open"),),
            ),
        ),
    )

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "Interesting fact" in markup


def test_callout_fills_are_pairwise_distinct() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert len({DEFINITION_FILL, FACT_FILL, FACTCHECK_FILL}) == 3
    assert f'fill: rgb("{DEFINITION_FILL}")' in markup
    assert f'fill: rgb("{FACT_FILL}")' in markup
    assert f'fill: rgb("{FACTCHECK_FILL}")' in markup


def test_callouts_are_unbreakable() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert markup.count("breakable: false") >= 3


def test_prose_is_justified_with_paragraph_spacing() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "justify: true" in markup


def test_inline_emphasis_renders_styled_without_literal_asterisks() -> None:
    notes = Notes(
        title="Лекция",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Введение",
                source_spans=(TimeRange(0.0, 10.0),),
                blocks=(
                    NoteBlock(kind=BlockKind.PROSE, text="Это **термин** в тексте"),
                ),
            ),
        ),
    )

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "**" not in markup
    assert '#text(weight: "bold", fill: rgb(' in markup
    assert ")[термин]" in markup


def test_inline_emphasis_escapes_special_characters_inside_markers() -> None:
    notes = Notes(
        title="Лекция",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Введение",
                source_spans=(TimeRange(0.0, 10.0),),
                blocks=(
                    NoteBlock(kind=BlockKind.PROSE, text="Про **тег #x и $y** дальше"),
                ),
            ),
        ),
    )

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert ")[тег \\#x и \\$y]" in markup


def test_unpaired_emphasis_marker_degrades_to_literal_text() -> None:
    notes = Notes(
        title="Лекция",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Введение",
                source_spans=(TimeRange(0.0, 10.0),),
                blocks=(
                    NoteBlock(kind=BlockKind.PROSE, text="Цена **растёт без пары"),
                ),
            ),
        ),
    )

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "\\*\\*растёт без пары" in markup


def test_typst_special_characters_in_user_text_are_escaped() -> None:
    notes = Notes(
        title="Лекция #1 про [скобки]",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="Символы * и _",
                source_spans=(TimeRange(0.0, 10.0),),
                blocks=(
                    NoteBlock(
                        kind=BlockKind.PROSE,
                        text="Цена $10, тег #tag, почта a@b.c, <угловые>, back\\slash",
                    ),
                ),
            ),
        ),
    )

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "\\#1" in markup
    assert "\\[скобки\\]" in markup
    assert "\\*" in markup
    assert "\\_" in markup
    assert "\\$10" in markup
    assert "\\#tag" in markup
    assert "a\\@b.c" in markup
    assert "\\<угловые\\>" in markup
    assert "back\\\\slash" in markup


def test_tall_figure_images_are_capped_in_height() -> None:
    notes = Notes(
        title="t",
        language="ru",
        sections=(
            NoteSection(
                section_id="s1",
                title="s",
                source_spans=(TimeRange(0.0, 1.0),),
                blocks=(
                    NoteBlock(
                        kind=BlockKind.FIGURE,
                        image_path="images/tall.png",
                        source_ref="generated:codex",
                        caption="c",
                    ),
                ),
            ),
        ),
    )

    markup = render_markup(notes, "lecture.mp4", "2026-08-22", a_metrics())

    assert 'image("images/tall.png", width: size.width)' in markup
    assert f'image("images/tall.png", height: {MAX_FIGURE_HEIGHT})' in markup


def test_title_page_carries_evidence_summary_rows() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    title_page = markup[: markup.index("#outline(")]
    assert "Длительность источника" in title_page
    assert "1:23:45" in title_page
    assert "Разделы" in title_page
    assert "3 + 2" in title_page
    assert "Иллюстрации" in title_page
    assert "Таблицы" in title_page
    assert "Схемы" in title_page
    assert "Вопросы для самопроверки" in title_page


def test_evidence_summary_shows_coverage_percent_with_one_decimal() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "Покрытие таймлайна" in markup
    assert "96.1%" in markup


def test_evidence_summary_counts_disputed_and_mixed_claims() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "Проверено утверждений" in markup
    assert "5 (disputed: 1, mixed: 1)" in markup


def test_evidence_summary_shows_bare_claim_count_when_none_flagged() -> None:
    notes = bilingual_notes()
    metrics = replace(a_metrics(), claims_disputed=0, claims_mixed=0)

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", metrics)

    assert "disputed" not in markup
    assert "mixed" not in markup


def test_evidence_summary_omits_chart_row_when_no_charts() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "Графики" not in markup[: markup.index("#outline(")]


def test_evidence_summary_shows_chart_row_when_charts_present() -> None:
    notes = bilingual_notes()
    metrics = replace(a_metrics(), chart_count=2)

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", metrics)

    assert "Графики" in markup[: markup.index("#outline(")]


def test_evidence_summary_omits_model_added_row_when_zero() -> None:
    notes = bilingual_notes()

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "Проверено добавлений модели" not in markup


def test_evidence_summary_shows_model_added_row_when_positive() -> None:
    notes = bilingual_notes()
    metrics = replace(a_metrics(), model_added_verified=3)

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", metrics)

    assert "Проверено добавлений модели" in markup


def test_evidence_summary_uses_english_labels_for_english_notes() -> None:
    notes = Notes(
        title="Probe lecture",
        language="en",
        sections=(
            NoteSection(
                section_id="s1",
                title="Intro",
                source_spans=(TimeRange(0.0, 10.0),),
                blocks=(NoteBlock(kind=BlockKind.PROSE, text=EN_PROSE_PROBE),),
            ),
        ),
    )

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", a_metrics())

    assert "Source duration" in markup
    assert "Timeline coverage" in markup
    assert "Quiz questions" in markup


def test_evidence_summary_of_zero_source_duration_reports_zero_coverage() -> None:
    notes = bilingual_notes()
    metrics = LectureMetrics(
        source_duration_seconds=0.0,
        accounted_duration_seconds=0.0,
        included_duration_seconds=0.0,
        cut_duration_seconds=0.0,
        section_count=0,
        subsection_count=0,
        figure_count=0,
        table_count=0,
        diagram_count=0,
        chart_count=0,
        claims_checked=0,
        claims_disputed=0,
        claims_mixed=0,
        model_added_verified=0,
        question_count=0,
    )

    markup = render_markup(notes, "lecture.mp4", "2026-08-19", metrics)

    assert "0.0%" in markup
    assert "0:00:00" in markup
