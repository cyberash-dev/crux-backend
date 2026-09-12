from collections.abc import Iterable

_MASK = "***"


class SecretValues:
    def __init__(self, values: Iterable[str]) -> None:
        self._values = tuple(sorted({value for value in values if value}, key=len, reverse=True))

    def masked(self, text: str) -> str:
        for value in self._values:
            text = text.replace(value, _MASK)
        return text
