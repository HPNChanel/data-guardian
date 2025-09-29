"""Structured logging setup for DG Core."""
from __future__ import annotations

import logging
from typing import Dict

import structlog

_DEFAULT_LEVEL = "info"


def configure_logging(level: str | None = None) -> None:
    """Configure structlog for the application."""
    log_level = (level or _DEFAULT_LEVEL).lower()
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        wrapper_class=structlog.make_filtering_bound_logger(_level_from_str(log_level)),
        cache_logger_on_first_use=True,
    )


def _level_from_str(level: str) -> int:
    mapping: Dict[str, int] = {
        "critical": logging.CRITICAL,
        "error": logging.ERROR,
        "warning": logging.WARNING,
        "info": logging.INFO,
        "debug": logging.DEBUG,
    }
    return mapping.get(level, logging.INFO)
