# In the name of God, the Most Gracious, the Most Merciful
"""Common CLI flags. Each server owns its entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp_app_core.app import AppDefinition


def add_common_arguments(parser: argparse.ArgumentParser, definition: AppDefinition) -> None:
    """Add the flags every server accepts."""

    parser.add_argument("--transport", choices=("stdio", "sse"), default=None)
    parser.add_argument("--workspace-root", type=Path, default=None)
    parser.add_argument("--log-folder", type=Path, default=None)
    parser.add_argument("--log-level", choices=("debug", "info", "warning", "error"), default=None)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--setup", action="store_true")
    parser.add_argument(
        "--version",
        action="version",
        version=f"{definition.name} (mcp-app-core)",
    )
