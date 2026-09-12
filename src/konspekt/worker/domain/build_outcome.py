from dataclasses import dataclass

from konspekt.worker.domain.failure_code import FailureCode

_SUCCESS_EXIT_CODE = 0
_INVALID_INVOCATION_EXIT_CODE = 2


@dataclass(frozen=True, slots=True)
class BuildOutcome:
    exit_code: int
    llm_spend_usd: float | None
    stderr_tail: str

    def failure_code(self) -> FailureCode | None:
        if self.exit_code == _SUCCESS_EXIT_CODE:
            return None
        if self.exit_code == _INVALID_INVOCATION_EXIT_CODE:
            return FailureCode.CONFIGURATION_ERROR
        return FailureCode.PIPELINE_FAILED
