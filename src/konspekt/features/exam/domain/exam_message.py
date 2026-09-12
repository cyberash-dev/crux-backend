from dataclasses import dataclass

from konspekt.features.exam.domain.message_role import MessageRole


@dataclass(frozen=True, slots=True)
class ExamMessage:
    role: MessageRole
    text: str
