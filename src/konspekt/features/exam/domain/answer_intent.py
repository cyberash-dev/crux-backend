from enum import StrEnum


class AnswerIntent(StrEnum):
    ANSWER = "answer"
    QUESTION = "question"
    OTHER = "other"
