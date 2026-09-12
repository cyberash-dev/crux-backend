import threading
from typing import Protocol


class BudgetExceededError(Exception):
    def __init__(self, spent_usd: float, max_usd: float, attempted_usd: float) -> None:
        super().__init__(
            f"BUDGET_EXCEEDED: spent {spent_usd:.2f} USD of {max_usd:.2f} USD, "
            f"next call estimated at {attempted_usd:.2f} USD"
        )
        self.spent_usd = spent_usd
        self.max_usd = max_usd
        self.attempted_usd = attempted_usd


class BudgetPort(Protocol):
    def charge(self, cost_usd: float) -> None: ...


class BudgetAccountant:
    def __init__(self, max_usd: float) -> None:
        self._max_usd = max_usd
        self._spent_usd = 0.0
        self._lock = threading.Lock()

    @property
    def spent_usd(self) -> float:
        return self._spent_usd

    def charge(self, cost_usd: float) -> None:
        with self._lock:
            if self._spent_usd + cost_usd > self._max_usd:
                raise BudgetExceededError(self._spent_usd, self._max_usd, cost_usd)
            self._spent_usd += cost_usd

    def ensure_not_exhausted(self) -> None:
        with self._lock:
            if self._spent_usd >= self._max_usd:
                raise BudgetExceededError(self._spent_usd, self._max_usd, 0.0)
