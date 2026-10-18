# In the name of God, the Most Gracious, the Most Merciful
"""Workspace path checks."""

from __future__ import annotations

from pathlib import Path

from mcp_app_core.errors import (
    AppError,
    ArtifactMissingError,
    SandboxViolationError,
    ValidationError,
)


def resolve_workspace_path(
    raw_path: str | Path,
    *,
    workspace_root: Path,
    sandbox_error: type[AppError] = SandboxViolationError,
) -> Path:
    """Resolve a path and reject anything outside the workspace root."""

    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    resolved = candidate.resolve(strict=False)
    root = workspace_root.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise sandbox_error(f"Path is outside workspace root: {resolved}")
    return resolved


def validate_existing_file(
    raw_path: str | Path,
    *,
    workspace_root: Path,
    suffixes: tuple[str, ...] = (),
    sandbox_error: type[AppError] = SandboxViolationError,
    validation_error: type[AppError] = ValidationError,
    missing_error: type[AppError] = ArtifactMissingError,
) -> Path:
    """Resolve an existing file inside the workspace."""

    resolved = resolve_workspace_path(
        raw_path, workspace_root=workspace_root, sandbox_error=sandbox_error
    )
    normalized = tuple(suffix.lower() for suffix in suffixes)
    if normalized and resolved.suffix.lower() not in normalized:
        suffix_list = ", ".join(normalized)
        raise validation_error(f"Expected one of {suffix_list}, got {resolved.suffix!r}")
    if not resolved.is_file():
        raise missing_error(f"File not found: {resolved}")
    return resolved


def resolve_output_path(
    raw_path: str | Path | None,
    *,
    workspace_root: Path,
    default: Path,
    suffixes: tuple[str, ...],
    sandbox_error: type[AppError] = SandboxViolationError,
    validation_error: type[AppError] = ValidationError,
) -> Path:
    """Resolve a writable output path inside the workspace."""

    if raw_path is None or raw_path == "":
        resolved = default.resolve(strict=False)
    else:
        resolved = resolve_workspace_path(
            raw_path, workspace_root=workspace_root, sandbox_error=sandbox_error
        )
    normalized = tuple(suffix.lower() for suffix in suffixes)
    if normalized and not any(resolved.name.lower().endswith(suffix) for suffix in normalized):
        suffix_list = ", ".join(normalized)
        raise validation_error(f"Output path must end in one of: {suffix_list}")
    return resolved


def validate_time_window(
    t_start: float | None,
    t_end: float | None,
    *,
    validation_error: type[AppError] = ValidationError,
) -> tuple[float | None, float | None]:
    """Reject a reversed time window."""

    if t_start is not None and t_end is not None and t_end < t_start:
        raise validation_error("t_end must be greater than or equal to t_start")
    return t_start, t_end
