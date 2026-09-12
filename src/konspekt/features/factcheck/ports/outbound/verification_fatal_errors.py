from konspekt.features.factcheck.ports.outbound.search_credential_error import (
    SearchCredentialError,
)
from konspekt.features.factcheck.ports.outbound.search_credits_exhausted_error import (
    SearchCreditsExhaustedError,
)
from konspekt.shared.budget import BudgetExceededError

VERIFICATION_FATAL_ERRORS: tuple[type[Exception], ...] = (
    BudgetExceededError,
    SearchCredentialError,
    SearchCreditsExhaustedError,
)
