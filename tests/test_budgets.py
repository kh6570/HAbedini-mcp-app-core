# In the name of God, the Most Gracious, the Most Merciful
"""Even spacing and minmax downsampling."""

from __future__ import annotations

import pytest

from mcp_app_core.budgets import DataBudget, downsample_indices, minmax_indices
from mcp_app_core.errors import BudgetExceededError, ValidationError


def test_even_spacing_keeps_the_endpoints() -> None:
    with pytest.raises(ValidationError):
        DataBudget(max_points=1)
    indexes = downsample_indices(10, 3)
    assert indexes == [0, 4, 9]
    assert downsample_indices(10, 4, strategy="lttb") == downsample_indices(10, 4)
    assert downsample_indices(10, 4, strategy="decimate") == downsample_indices(10, 4)


def test_minmax_keeps_each_bucket_extreme() -> None:
    series = [0, 0, 5, 0, 0, -4, 0, 0]
    assert minmax_indices(series, 6) == [0, 1, 2, 5, 6, 7]
    assert downsample_indices(8, 6) == [0, 1, 3, 4, 6, 7]
    assert downsample_indices(8, 6, strategy="lttb", values=series) == [0, 1, 3, 4, 6, 7]


def test_minmax_uses_the_spare_slot_for_the_farthest_sample() -> None:
    series = [0, 0, 10, 0, 0, 0, 0]
    assert minmax_indices(series, 3) == [0, 2, 6]


def test_minmax_strategy_is_what_the_budget_uses() -> None:
    values = [0.0] * 50
    values[3] = 25.0
    values[40] = -30.0
    budget = DataBudget(max_points=2000, max_bytes=1024, strategy="minmax")
    chosen = budget.select_indices(len(values), values=values, dtype_size=128)
    assert chosen[0] == 0
    assert chosen[-1] == 49
    assert 3 in chosen
    assert 40 in chosen
    assert len(chosen) <= 8
    assert chosen == sorted(set(chosen))
    even = downsample_indices(50, 8)
    assert 3 not in even
    assert 40 not in even

    plain = DataBudget(max_points=10)
    assert plain.strategy == "lttb"
    assert plain.select_indices(50) == downsample_indices(50, 10)


def test_minmax_requires_values_only_when_downsampling() -> None:
    budget = DataBudget(max_points=10, strategy="minmax")
    assert budget.select_indices(4) == [0, 1, 2, 3]
    with pytest.raises(ValidationError, match="minmax"):
        budget.select_indices(50)
    with pytest.raises(ValidationError, match="one sample"):
        downsample_indices(4, 3, strategy="minmax", values=[1.0, 2.0])
    assert minmax_indices([1.0, 2.0, 3.0], 10) == [0, 1, 2]


def test_minmax_skips_non_finite_samples_and_rejects_bools() -> None:
    chosen = minmax_indices([0.0, float("nan"), 4.0, float("nan"), 0.0], 4)
    assert chosen[0] == 0
    assert chosen[-1] == 4
    assert 2 in chosen
    assert 1 not in chosen
    assert 3 not in chosen
    with pytest.raises(ValidationError, match="real"):
        minmax_indices([True, False, True, False], 3)  # type: ignore[list-item]
    with pytest.raises(BudgetExceededError):
        minmax_indices([1.0, 2.0, 3.0, 4.0], 1)


def test_unknown_strategy_is_rejected() -> None:
    with pytest.raises(ValidationError, match="average"):
        downsample_indices(8, 4, strategy="average")  # type: ignore[arg-type]
