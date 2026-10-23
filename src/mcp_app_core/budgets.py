# In the name of God, the Most Gracious, the Most Merciful
"""Size budgets for data returned to an MCP client."""

from __future__ import annotations

import math
from collections.abc import Sequence
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

    def select_indices(
        self,
        n_points: int,
        *,
        values: Sequence[float] | None = None,
        dtype_size: int = 8,
    ) -> list[int]:
        """Return the indices this budget keeps for ``strategy``.

        A series that already fits is returned in full. ``minmax`` then keeps
        per-bucket extremes and requires ``values``. ``lttb`` and ``decimate``
        keep evenly spaced samples.
        """

        if n_points < 0:
            raise ValidationError("n_points must be zero or greater.")
        target = self.target_points(n_points, dtype_size)
        if n_points <= target:
            return list(range(n_points))
        return downsample_indices(n_points, target, strategy=self.strategy, values=values)


DEFAULT_BUDGET = DataBudget()


def _even_indices(n_points: int, target: int) -> list[int]:
    """Return evenly spaced indices, including the first and last samples.

    ``decimate`` uses this spacing. ``lttb`` uses it too, because a
    Largest-Triangle-Three-Buckets pass is not included.
    """

    if target < 2:
        raise BudgetExceededError("Downsampling target must keep at least two points.")
    if n_points <= target:
        return list(range(n_points))
    if n_points < 2:
        raise BudgetExceededError("Series has fewer than two points.")
    last = n_points - 1
    span = target - 1
    return [round(index * last / span) for index in range(target)]


def _real_samples(values: Sequence[float]) -> tuple[float, ...]:
    samples: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValidationError("minmax downsampling requires real sample values.")
        samples.append(float(value))
    return tuple(samples)


def _bucket_extrema(values: Sequence[float], start: int, end: int) -> tuple[int, int]:
    finite = [index for index in range(start, end) if math.isfinite(values[index])]
    pool = finite if finite else [start]
    min_index = pool[0]
    max_index = pool[0]
    for index in pool[1:]:
        value = values[index]
        if value < values[min_index]:
            min_index = index
        if value >= values[max_index]:
            max_index = index
    return min_index, max_index


def _fit_target(indices: Sequence[int], target: int) -> list[int]:
    unique = sorted(set(indices))
    if len(unique) <= target:
        return unique
    middle = unique[1:-1][: target - 2]
    return [unique[0], *middle, unique[-1]]


def _farthest_from_chord(values: Sequence[float], chosen: set[int], last_index: int) -> int | None:
    """Return the interior index farthest from the line between the endpoints."""

    first_value = values[0]
    last_value = values[last_index]
    if last_index <= 0 or not math.isfinite(first_value) or not math.isfinite(last_value):
        return None
    best_index: int | None = None
    best_distance = -1.0
    for index in range(1, last_index):
        if index in chosen:
            continue
        value = values[index]
        if not math.isfinite(value):
            continue
        baseline = first_value + (last_value - first_value) * (index / last_index)
        distance = abs(value - baseline)
        if distance > best_distance:
            best_distance = distance
            best_index = index
    return best_index


def minmax_indices(values: Sequence[float], target: int) -> list[int]:
    """Keep endpoints and each interior bucket's minimum and maximum.

    The open interval between the endpoints is split into ``(target - 2) // 2``
    buckets. Each bucket contributes its minimum and maximum in index order.
    When one slot is left over, it keeps the interior sample farthest from the
    line between the endpoints. The result is never longer than ``target``.
    """

    samples = _real_samples(values)
    count = len(samples)
    if target < 2:
        raise BudgetExceededError("Downsampling target must keep at least two points.")
    if count <= target:
        return list(range(count))
    if count < 2:
        raise BudgetExceededError("Series has fewer than two points.")

    last_index = count - 1
    selected: list[int] = [0]
    interior = count - 2
    bucket_count = min((target - 2) // 2, interior)
    for bucket in range(bucket_count):
        start = 1 + (bucket * interior) // bucket_count
        end = 1 + ((bucket + 1) * interior) // bucket_count
        if start >= end:
            continue
        low, high = _bucket_extrema(samples, start, end)
        selected.extend((low, high) if low <= high else (high, low))
    selected.append(last_index)
    fitted = _fit_target(selected, target)
    if len(fitted) < target:
        extra = _farthest_from_chord(samples, set(fitted), last_index)
        if extra is not None:
            fitted = _fit_target([*fitted, extra], target)
    return fitted


def downsample_indices(
    n_points: int,
    target: int,
    *,
    strategy: DownsampleStrategy = "lttb",
    values: Sequence[float] | None = None,
) -> list[int]:
    """Return indices for one downsample strategy.

    ``minmax`` requires ``values`` and keeps each bucket's minimum and maximum
    plus both endpoints. ``decimate`` returns evenly spaced indices. ``lttb``
    returns those same evenly spaced indices; a Largest-Triangle-Three-Buckets
    pass is not included.
    """

    if strategy == "minmax":
        if values is None:
            raise ValidationError("minmax downsampling requires one value per point.")
        if len(values) != n_points:
            raise ValidationError("minmax values must contain one sample per point.")
        return minmax_indices(values, target)
    if strategy in {"lttb", "decimate"}:
        return _even_indices(n_points, target)
    raise ValidationError(f"Unknown downsample strategy {strategy!r}.")
