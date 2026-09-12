from typing import Protocol


class RunningJobPort[T](Protocol):
    def outcome(self) -> T | None:
        """None while the job still runs."""
        ...

    def terminate(self) -> None: ...
