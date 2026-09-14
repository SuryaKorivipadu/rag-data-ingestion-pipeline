"""Shared console and rotating-file logging for Airflow support scripts."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


DEFAULT_LOG_PATH = Path(__file__).resolve().parents[1] / "logs"
LOG_PATH = Path(os.getenv("AIRFLOW_LOG_PATH", str(DEFAULT_LOG_PATH)))
LOG_PATH.mkdir(parents=True, exist_ok=True)


_old_record_factory = logging.getLogRecordFactory()


def _record_factory(*args, **kwargs):
    """Add a workspace-relative module path to each log record."""
    record = _old_record_factory(*args, **kwargs)
    record.module_path = os.path.relpath(record.pathname).replace(os.sep, ".")
    if record.module_path.endswith(".py"):
        record.module_path = record.module_path[:-3]
    return record


logging.setLogRecordFactory(_record_factory)


def _log_level() -> int:
    """Return the configured log level, defaulting safely to INFO."""
    configured_level = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, configured_level, logging.INFO)


def get_logger(name: str = "airflow") -> logging.Logger:
    """Return a configured console and rotating-file logger."""
    logger = logging.getLogger(name)
    logger.setLevel(_log_level())
    logger.propagate = False

    if logger.handlers:
        return logger

    log_format = (
        "%(asctime)s | %(levelname)s | %(name)s | %(module_path)s | "
        "%(filename)s:%(lineno)d | %(funcName)s | %(message)s"
    )
    formatter = logging.Formatter(log_format)

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
