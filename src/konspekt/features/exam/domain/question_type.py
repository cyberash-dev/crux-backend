from enum import StrEnum


class QuestionType(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTI_SELECT = "multi_select"
    OPEN = "open"
