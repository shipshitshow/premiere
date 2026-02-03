"""Logging configuration for Premiere."""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.logging import RichHandler


LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_console = Console(stderr=True)
_logger: logging.Logger | None = None


class LogConfig:
    """Logging configuration settings."""

    def __init__(
        self,
        level: LogLevel = "INFO",
        log_file: Path | None = None,
        log_to_file: bool = False,
        log_dir: Path | None = None,
        max_log_files: int = 10,
        include_timestamp_in_filename: bool = True,
        show_path: bool = False,
        show_locals_in_tracebacks: bool = False,
    ):
        self.level = level
        self.log_file = log_file
        self.log_to_file = log_to_file
        self.log_dir = log_dir
        self.max_log_files = max_log_files
        self.include_timestamp_in_filename = include_timestamp_in_filename
        self.show_path = show_path
        self.show_locals_in_tracebacks = show_locals_in_tracebacks


def setup_logger(
    name: str = "premiere",
    level: LogLevel = "INFO",
    log_file: Path | None = None,
    config: LogConfig | None = None,
) -> logging.Logger:
    """Configure and return the application logger.

    Args:
        name: Logger name.
        level: Logging level (overridden by config if provided).
        log_file: Optional file path for logging (overridden by config if provided).
        config: Optional LogConfig for advanced configuration.

    Returns:
        Configured logger instance.
    """
    global _logger

    if _logger is not None:
        return _logger

    # Use config values if provided
    cfg = config or LogConfig(level=level, log_file=log_file)

    # Check for environment variable override
    env_level = os.environ.get("PREMIERE_LOG_LEVEL", "").upper()
    if env_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        cfg.level = env_level  # type: ignore

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, cfg.level))
    logger.handlers.clear()

    # Rich console handler
    console_handler = RichHandler(
        console=_console,
        show_time=True,
        show_path=cfg.show_path,
        rich_tracebacks=True,
        tracebacks_show_locals=cfg.show_locals_in_tracebacks,
        markup=True,
    )
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    # File handler if specified or auto-logging enabled
    file_path = cfg.log_file
    if file_path is None and cfg.log_to_file:
        log_dir = cfg.log_dir or Path.cwd() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        if cfg.include_timestamp_in_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = log_dir / f"premiere_{timestamp}.log"
        else:
            file_path = log_dir / "premiere.log"

        # Cleanup old log files
        _cleanup_old_logs(log_dir, cfg.max_log_files)

    if file_path:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
            )
        )
        file_handler.setLevel(logging.DEBUG)  # File gets all messages
        logger.addHandler(file_handler)

    _logger = logger
    return logger


def _cleanup_old_logs(log_dir: Path, max_files: int) -> None:
    """Remove old log files keeping only the most recent ones.

    Args:
        log_dir: Directory containing log files.
        max_files: Maximum number of log files to keep.
    """
    log_files = sorted(
        log_dir.glob("premiere_*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for old_file in log_files[max_files:]:
        try:
            old_file.unlink()
        except OSError:
            pass  # Ignore errors deleting old logs


def get_logger() -> logging.Logger:
    """Get the application logger, creating it if necessary."""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


def get_console() -> Console:
    """Get the rich console instance."""
    return _console


def set_log_level(level: LogLevel) -> None:
    """Change the logging level at runtime.

    Args:
        level: New logging level.
    """
    logger = get_logger()
    logger.setLevel(getattr(logging, level))
    for handler in logger.handlers:
        if isinstance(handler, RichHandler):
            handler.setLevel(getattr(logging, level))
