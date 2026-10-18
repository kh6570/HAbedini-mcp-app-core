# In the name of God, the Most Gracious, the Most Merciful
"""Configurable framework for local MCP servers."""

from __future__ import annotations

from mcp_app_core.app import AppDefinition
from mcp_app_core.errors import AppError

__all__ = ["AppDefinition", "AppError", "__version__"]

__version__ = "0.1.0"
