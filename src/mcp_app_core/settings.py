# In the name of God, the Most Gracious, the Most Merciful
"""Settings whose environment prefix comes from the server definition."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal, Self

from platformdirs import user_cache_dir
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_app_core.app import AppDefinition


class AppSettings(BaseSettings):
    """Common settings. Subclasses set ``model_config`` for their env prefix."""

    exe: Path | None = None
    transport: Literal["stdio", "sse"] = "stdio"
    enable_sse: bool = False
    workspace_root: Path = Path.cwd()
    cache_dir: Path | None = None
    log_folder: Path | None = None
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    timeout_s: float | None = 120.0
    max_cache_bytes: int | None = None

    cache_app_name: ClassVar[str] = "mcp-app-core"

    def normalized(self) -> Self:
        """Return a copy with absolute paths and a default cache directory."""

        cache_dir = self.cache_dir or Path(user_cache_dir(self.cache_app_name))
        exe = self.exe.resolve(strict=False) if self.exe is not None else None
        log_folder = self.log_folder.resolve(strict=False) if self.log_folder is not None else None
        return self.model_copy(
            update={
                "exe": exe,
                "workspace_root": self.workspace_root.resolve(strict=False),
                "cache_dir": cache_dir.resolve(strict=False),
                "log_folder": log_folder,
            }
        )

    def resolve_timeout_s(self, explicit: float | None) -> float | None:
        """Return an explicit timeout, or the configured default.

        Non-positive values disable the timeout.
        """

        if explicit is not None:
            return None if explicit <= 0 else explicit
        if self.timeout_s is not None and self.timeout_s <= 0:
            return None
        return self.timeout_s


def make_settings_class(definition: AppDefinition) -> type[AppSettings]:
    """Build a settings class that reads ``definition.env_prefix`` variables."""

    class Settings(AppSettings):
        cache_app_name: ClassVar[str] = definition.cache_name
        model_config = SettingsConfigDict(
            env_prefix=definition.env_prefix,
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

    Settings.__name__ = f"{definition.name.replace('-', '_').title()}Settings"
    Settings.__qualname__ = Settings.__name__
    return Settings
