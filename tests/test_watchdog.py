# In the name of God, the Most Gracious, the Most Merciful
"""Watchdog process checks. No simulator is required."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from mcp_app_core.watchdog import is_process_alive, run_watchdog


def test_current_process_is_alive() -> None:
    assert is_process_alive(os.getpid()) is True


def test_nonpositive_pid_is_not_alive() -> None:
    assert is_process_alive(0) is False
    assert is_process_alive(-1) is False


@pytest.mark.skipif(not Path("/proc").is_dir(), reason="zombie state is read from /proc")
def test_unreaped_exited_child_is_not_alive() -> None:
    process = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(0)"])
    try:
        deadline = time.monotonic() + 5
        state = ""
        while time.monotonic() < deadline:
            stat_path = Path(f"/proc/{process.pid}/stat")
            try:
                data = stat_path.read_text(encoding="ascii", errors="replace")
            except FileNotFoundError:
                state = "X"
            else:
                state = data.rsplit(")", 1)[1].split(None, 1)[0]
            if state in {"Z", "X"}:
                break
            time.sleep(0.02)
        assert is_process_alive(process.pid) is False
    finally:
        process.wait(timeout=5)


def test_watchdog_returns_after_parent_exits() -> None:
    parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.2)"])
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        reaped = run_watchdog(
            parent_pid=parent.pid,
            child_pids=(child.pid,),
            poll_interval_s=0.05,
            grace_s=2.0,
        )
        assert child.pid in reaped
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
