# @covers pipeline:POL-002
import pytest

from konspekt.shared.budget import BudgetAccountant, BudgetExceededError


def test_charges_accumulate_under_the_limit() -> None:
    accountant = BudgetAccountant(max_usd=10.0)

    accountant.charge(4.0)
    accountant.charge(6.0)

    assert accountant.spent_usd == 10.0


def test_charge_beyond_limit_raises_before_recording() -> None:
    accountant = BudgetAccountant(max_usd=10.0)
    accountant.charge(9.0)

    with pytest.raises(BudgetExceededError, match="BUDGET_EXCEEDED"):
        accountant.charge(1.5)

    assert accountant.spent_usd == 9.0


def test_zero_budget_rejects_first_charge() -> None:
    accountant = BudgetAccountant(max_usd=0.0)

    with pytest.raises(BudgetExceededError, match="BUDGET_EXCEEDED"):
        accountant.charge(0.01)


def test_ensure_not_exhausted_passes_while_budget_remains() -> None:
    accountant = BudgetAccountant(max_usd=10.0)
    accountant.charge(9.99)

    accountant.ensure_not_exhausted()


def test_ensure_not_exhausted_raises_once_budget_is_spent() -> None:
    accountant = BudgetAccountant(max_usd=10.0)
    accountant.charge(10.0)

    with pytest.raises(BudgetExceededError, match="BUDGET_EXCEEDED"):
        accountant.ensure_not_exhausted()


def test_concurrent_charges_are_not_lost() -> None:
    from concurrent.futures import ThreadPoolExecutor

    accountant = BudgetAccountant(max_usd=1000.0)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for _ in range(200):
            pool.submit(accountant.charge, 1.0)

    assert accountant.spent_usd == 200.0
