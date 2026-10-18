# In the name of God, the Most Gracious, the Most Merciful
"""Subprocess timeout and Windows process-tree stop."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from mcp_app_core.errors import AppError, OperationTimeoutError


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Completed child-process summary."""

    command: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str


def kill_process_tree(process: subprocess.Popen[str]) -> None:
    """Stop a child and any processes it spawned."""

    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(  # noqa: S603
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
        )
        return
    process.kill()


def run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout_s: float | None,
    timeout_error: type[AppError] = OperationTimeoutError,
    start_error: type[AppError] = AppError,
    on_start: Callable[[subprocess.Popen[str]], None] | None = None,
) -> CommandResult:
    """Run one command and enforce the timeout."""

    try:
        process = subprocess.Popen(  # noqa: S603
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise start_error(f"Failed to start process: {exc}") from exc
    if on_start is not None:
        on_start(process)
    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        kill_process_tree(process)
        process.wait(timeout=10)
        raise timeout_error(f"Process exceeded the timeout of {timeout_s} seconds.") from exc
    return CommandResult(
        command=tuple(command),
        return_code=int(process.returncode or 0),
        stdout=stdout or "",
        stderr=stderr or "",
    )
