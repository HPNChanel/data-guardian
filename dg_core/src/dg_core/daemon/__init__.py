"""Daemon utilities for DG Core."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .log_stream import get_log_stream

__all__ = ["DaemonServer", "get_log_stream", "main"]


def __getattr__(name: str) -> Any:  # pragma: no cover - thin wrapper
    if name in {"DaemonServer", "main"}:
        from .server import DaemonServer, main

        globals().update({"DaemonServer": DaemonServer, "main": main})
        return globals()[name]
    raise AttributeError(name)


if TYPE_CHECKING:  # pragma: no cover - typing aid
    from .server import DaemonServer, main  # noqa: F401
