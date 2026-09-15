"""Shared console and rotating-file logging for the service."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


DEFAULT_LOG_PATH = Path(__file__).resolve().parents[2] / "logs"
LOG_PATH = Path(os.getenv("LOG_PATH", str(DEFAULT_LOG_PATH)))
LOG_PATH.mkdir(parents=True, exist_ok=True)


_old_record_factory = logging.getLogRecordFactory()


def _record_factory(*args, **kwargs):
    """Add a relative module path to each log record."""
    record = _old_record_factory(*args, **kwargs)
    record.module_path = os.path.relpath(record.pathname).replace(os.sep, ".")
    if record.module_path.endswith(".py"):
        record.module_path = record.module_path[:-3]
    return record


logging.setLogRecordFactory(_record_factory)


def _log_level() -> int:
    """Return the configured log level, defaulting to INFO."""
    return getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)


def get_logger(name: str = "read_and_chunk") -> logging.Logger:
    """Return a logger with console and rotating-file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(_log_level())
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(module_path)s | "
        "%(filename)s:%(lineno)d | %(funcName)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(_log_level())
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        LOG_PATH / "app.log",
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(_log_level())
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
