"""Structured logging setup for DG Core."""
from __future__ import annotations

import logging
import sys
from typing import Dict

import structlog

from .daemon.log_stream import get_log_stream, stream_processor

_DEFAULT_LEVEL = "info"


def configure_logging(level: str | None = None) -> None:
    """Configure structlog for the application.

    The configuration emits JSON lines with the keys ``level``, ``ts``, ``msg`` and
    ``component`` while still preserving any additional context supplied by callers.
    ``log_stream`` subscribers are notified via a dedicated structlog processor so
    that the daemon can forward log entries to connected clients without blocking
    the logging pipeline.
    """

    log_level = (level or _DEFAULT_LEVEL).lower()
    numeric_level = _level_from_str(log_level)

    logging.basicConfig(
        level=numeric_level,
        handlers=[logging.StreamHandler(sys.stdout)],
        format="%(message)s",
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", key="ts"),
            structlog.stdlib.add_log_level,
            _component_processor,
            _rename_event_to_msg,
            stream_processor(get_log_stream()),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=True,
    )


def _component_processor(
    logger: structlog.BoundLoggerBase, _name: str, event_dict: dict[str, object]
) -> dict[str, object]:
    """Ensure every log record carries a ``component`` field."""

    component = event_dict.get("component")
    if component is None:
        logger_name = getattr(logger, "name", None) or "dg_core"
        event_dict["component"] = logger_name
    return event_dict


def _rename_event_to_msg(
    _logger: structlog.BoundLoggerBase, _name: str, event_dict: dict[str, object]
) -> dict[str, object]:
    """Normalize the event field to ``msg`` for downstream consumers."""

    if "msg" not in event_dict:
        event = event_dict.pop("event", "")
        event_dict["msg"] = event
    return event_dict


def _level_from_str(level: str) -> int:
    mapping: Dict[str, int] = {
        "critical": logging.CRITICAL,
        "error": logging.ERROR,
        "warning": logging.WARNING,
        "info": logging.INFO,
        "debug": logging.DEBUG,
    }
    return mapping.get(level, logging.INFO)


__all__ = ["configure_logging"]
