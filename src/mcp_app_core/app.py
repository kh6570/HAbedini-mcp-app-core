# In the name of God, the Most Gracious, the Most Merciful
"""Identity and configuration for one MCP server built on this framework."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppDefinition:
    """Values that differ between servers and stay out of the framework."""

    name: str
    title: str
    env_prefix: str
    default_error_code: str
    instructions: str
    cache_name: str
    service_packages: tuple[str, ...]
    executable_parameter: str = "executable"
    extra_contract_modules: tuple[str, ...] = ()
