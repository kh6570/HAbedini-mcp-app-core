# In the name of God, the Most Gracious, the Most Merciful
"""Structured logging shared by servers."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

Logger = structlog.stdlib.BoundLogger


def configure_logging(
    level: str = "info",
    *,
    log_folder: Path | None = None,
    file_name: str = "mcp-app.log",
) -> None:
    """Configure stdlib and structlog once per process."""

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=numeric_level, format="%(message)s")
    if log_folder is not None:
        log_folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_folder / file_name,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setLevel(numeric_level)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(handler)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=False),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str, **context: object) -> Logger:
    """Return a bound logger."""

    logger: Logger = structlog.get_logger(name)
    if context:
        return logger.bind(**context)
    return logger
