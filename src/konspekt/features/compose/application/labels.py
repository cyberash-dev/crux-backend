from collections.abc import Mapping

LABELS_BY_LANGUAGE: Mapping[str, Mapping[str, str]] = {
    "ru": {
        "contents": "Содержание",
        "source_label": "Источник",
        "factcheck_label": "Проверка факта",
        "fact_label": "Интересный факт",
        "section_label": "Раздел",
        "generated_label": "Иллюстрация сгенерирована ИИ",
        "claims_title": "Проверка фактов",
        "cut_log_title": "Вырезанные фрагменты",
        "bundle_note": (
            "Конспект лекции для изучения агентом: прочитайте файлы разделов по "
            "порядку оглавления; определения и факты выделены цитатами, схемы даны в "
            "формате mermaid, проверенные утверждения собраны в claims.md, "
            "вырезанные отступления — в cut-log.md. Вопросы для самопроверки лежат "
            "рядом в quiz.json (section_id указывает на файл раздела)."
        ),
        "source_video": "Исходное видео",
        "generated_on": "Дата генерации",
        "language": "Язык",
        "claim": "Утверждение",
        "time": "Время",
        "verdict": "Вердикт",
        "annotation": "Комментарий",
        "sources": "Источники",
        "label": "Метка",
        "reason": "Причина",
        "chart_kind": "График",
        "claim_id": "ID",
        "correction": "Исправление",
        "text": "Текст",
        "kind": "Тип",
        "origin": "Происхождение",
        "action": "Действие",
        "model_added_title": "Добавлено моделью",
        "metrics_source_duration": "Длительность источника",
        "metrics_accounted_duration": "Учтено в конспекте",
        "metrics_included_duration": "Включено",
        "metrics_cut_duration": "Вырезано",
        "metrics_sections": "Разделы",
        "metrics_figures": "Иллюстрации",
        "metrics_tables": "Таблицы",
        "metrics_diagrams": "Схемы",
        "metrics_charts": "Графики",
        "metrics_claims_checked": "Проверено утверждений",
        "metrics_model_added": "Проверено добавлений модели",
        "metrics_questions": "Вопросы для самопроверки",
        "metrics_coverage": "Покрытие таймлайна",
    },
    "en": {
        "contents": "Contents",
        "source_label": "Source",
        "factcheck_label": "Fact check",
        "fact_label": "Interesting fact",
        "section_label": "Section",
        "generated_label": "AI-generated illustration",
        "claims_title": "Fact check",
        "cut_log_title": "Cut log",
        "bundle_note": (
            "Lecture notes for an agent to study: read the section files in outline "
            "order; definitions and facts are blockquotes, diagrams are mermaid "
            "blocks, checked claims are collected in claims.md and removed "
            "digressions in cut-log.md. Self-check questions live next to this "
            "bundle in quiz.json (section_id points at a section file)."
        ),
        "source_video": "Source video",
        "generated_on": "Generated on",
        "language": "Language",
        "claim": "Claim",
        "time": "Time",
        "verdict": "Verdict",
        "annotation": "Annotation",
        "sources": "Sources",
        "label": "Label",
        "reason": "Reason",
        "chart_kind": "Chart",
        "claim_id": "ID",
        "correction": "Correction",
        "text": "Text",
        "kind": "Kind",
        "origin": "Origin",
        "action": "Action",
        "model_added_title": "Model-added",
        "metrics_source_duration": "Source duration",
        "metrics_accounted_duration": "Accounted",
        "metrics_included_duration": "Included",
        "metrics_cut_duration": "Cut",
        "metrics_sections": "Sections",
        "metrics_figures": "Figures",
        "metrics_tables": "Tables",
        "metrics_diagrams": "Diagrams",
        "metrics_charts": "Charts",
        "metrics_claims_checked": "Claims checked",
        "metrics_model_added": "Model-added verified",
        "metrics_questions": "Quiz questions",
        "metrics_coverage": "Timeline coverage",
    },
}


def labels_for(language: str) -> Mapping[str, str]:
    return LABELS_BY_LANGUAGE.get(language, LABELS_BY_LANGUAGE["en"])
