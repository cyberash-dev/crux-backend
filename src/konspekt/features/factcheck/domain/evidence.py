from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Evidence:
    url: str
    title: str
    published_date: str | None
    excerpts: tuple[str, ...]
