"""Logging configuration for Premiere."""

import logging
import sys
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.logging import RichHandler


LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_console = Console(stderr=True)
_logger: logging.Logger | None = None


def setup_logger(
    name: str = "premiere",
    level: LogLevel = "INFO",
    log_file: Path | None = None,
) -> logging.Logger:
    """Configure and return the application logger.

    Args:
        name: Logger name.
        level: Logging level.
        log_file: Optional file path for logging.

    Returns:
        Configured logger instance.
    """
    global _logger

    if _logger is not None:
        return _logger

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    logger.handlers.clear()

    # Rich console handler
    console_handler = RichHandler(
        console=_console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
    )
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """Get the application logger, creating it if necessary."""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


def get_console() -> Console:
    """Get the rich console instance."""
    return _console
