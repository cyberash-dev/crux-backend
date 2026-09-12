from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...
