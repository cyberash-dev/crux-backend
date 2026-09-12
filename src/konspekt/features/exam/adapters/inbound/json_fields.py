from collections.abc import Mapping, Sequence
from enum import StrEnum

from konspekt.features.exam.adapters.inbound.exam_input_error import ExamInputError


def json_object(raw_value: object, label: str) -> Mapping[str, object]:
    if not isinstance(raw_value, dict):
        raise ExamInputError(f"{label} must be a JSON object")
    return raw_value


def json_list(raw_value: object, label: str) -> Sequence[object]:
    if not isinstance(raw_value, list):
        raise ExamInputError(f"{label} must be a JSON array")
    return raw_value


def json_text(raw_value: object, label: str) -> str:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ExamInputError(f"{label} must be a non-empty string")
    return raw_value


def json_count(raw_value: object, label: str, minimum: int) -> int:
    if (
        isinstance(raw_value, bool)
        or not isinstance(raw_value, int)
        or raw_value < minimum
    ):
        raise ExamInputError(f"{label} must be an integer >= {minimum}")
    return raw_value


def json_seconds(raw_value: object, label: str) -> float:
    if (
        isinstance(raw_value, bool)
        or not isinstance(raw_value, int | float)
        or raw_value < 0
    ):
        raise ExamInputError(f"{label} must be a non-negative number")
    return float(raw_value)


def json_enum[EnumType: StrEnum](
    enum_type: type[EnumType], raw_value: object, label: str
) -> EnumType:
    try:
        return enum_type(raw_value)
    except ValueError as error:
        allowed_values = ", ".join(member.value for member in enum_type)
        raise ExamInputError(f"{label} must be one of {allowed_values}") from error
