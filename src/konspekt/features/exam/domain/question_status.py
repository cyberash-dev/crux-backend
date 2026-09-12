from enum import StrEnum


class QuestionStatus(StrEnum):
    PENDING = "pending"
    FAILED = "failed"
    MASTERED = "mastered"
