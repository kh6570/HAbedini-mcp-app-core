# In the name of God, the Most Gracious, the Most Merciful
"""Size budgets for data returned to an MCP client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mcp_app_core.errors import BudgetExceededError, ValidationError

DownsampleStrategy = Literal["lttb", "decimate", "minmax"]
_MIN_POINTS = 3
_MIN_BYTES = 1024


@dataclass(frozen=True, slots=True)
class DataBudget:
    """Limits how much data a tool may return."""

    max_points: int = 2000
    max_bytes: int = 64_000
    strategy: DownsampleStrategy = "lttb"

    def __post_init__(self) -> None:
        if self.max_points < _MIN_POINTS:
            raise ValidationError(f"max_points must be >= {_MIN_POINTS}")
        if self.max_bytes < _MIN_BYTES:
            raise ValidationError(f"max_bytes must be >= {_MIN_BYTES}")

    def fits(self, n_points: int, dtype_size: int = 8) -> bool:
        """Return True when n_points samples fit both caps."""

        return n_points <= self.max_points and n_points * dtype_size <= self.max_bytes

    def target_points(self, n_points: int, dtype_size: int = 8) -> int:
        """Return the largest sample count that fits both caps."""

        by_points = min(n_points, self.max_points)
        by_bytes = self.max_bytes // dtype_size
        return min(by_points, by_bytes)


DEFAULT_BUDGET = DataBudget()


def downsample_indices(n_points: int, target: int) -> list[int]:
    """Return inclusive linspace indices that keep the first and last samples."""

    if target < 2:
        raise BudgetExceededError("Downsampling target must keep at least two points.")
    if n_points <= target:
        return list(range(n_points))
    if n_points < 2:
        raise BudgetExceededError("Series has fewer than two points.")
    last = n_points - 1
    span = target - 1
    return [round(index * last / span) for index in range(target)]
