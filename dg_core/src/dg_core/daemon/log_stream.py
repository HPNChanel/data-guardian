"""Utilities for streaming DG Core logs to connected clients."""
from __future__ import annotations

import asyncio
from asyncio import Queue
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, Iterable


@dataclass(slots=True)
class LogSubscription:
    """Asynchronous iterator over log records."""

    _stream: "LogStream"
    _queue: Queue[Dict[str, Any]]
    _closed: bool = False

    def __aiter__(self) -> "LogSubscription":
        return self

    async def __anext__(self) -> Dict[str, Any]:
        if self._closed:
            raise StopAsyncIteration
        try:
            record = await self._queue.get()
        except asyncio.CancelledError:  # pragma: no cover - cooperative cancellation
            self._closed = True
            raise
        if record is _SENTINEL:
            self._closed = True
            raise StopAsyncIteration
        return record

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._stream._remove(self._queue)


_SentinelType = object
_SENTINEL = _SentinelType()


class LogStream:
    """Fan-out publisher for structured log records."""

    def __init__(self, *, max_queue: int = 256, backlog: int = 128) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: Dict[int, Queue[Dict[str, Any]]] = {}
        self._max_queue = max_queue
        self._backlog: Deque[Dict[str, Any]] = deque(maxlen=backlog)
        self._pending: Deque[Dict[str, Any]] = deque(maxlen=backlog)

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        while self._pending:
            record = self._pending.popleft()
            self._dispatch(record)

    def publish(self, record: Dict[str, Any]) -> None:
        payload = dict(record)
        self._backlog.append(payload)
        if self._loop is None:
            self._pending.append(payload)
            return
        self._loop.call_soon_threadsafe(self._dispatch, payload)

    def subscribe(self) -> LogSubscription:
        if self._loop is None:
            raise RuntimeError("Log stream not attached to an event loop")
        queue: Queue[Dict[str, Any]] = Queue(maxsize=self._max_queue)
        # prime the queue with the backlog without exceeding maxsize
        for item in list(self._backlog)[-self._max_queue :]:
            if queue.full():
                break
            queue.put_nowait(item)
        self._subscribers[id(queue)] = queue
        return LogSubscription(self, queue)

    async def _remove(self, queue: Queue[Dict[str, Any]]) -> None:
        self._subscribers.pop(id(queue), None)
        try:
            queue.put_nowait(_SENTINEL)  # type: ignore[arg-type]
        except asyncio.QueueFull:
            pass

    def _dispatch(self, record: Dict[str, Any]) -> None:
        for queue in list(self._subscribers.values()):
            self._enqueue(queue, record)

    def _enqueue(self, queue: Queue[Dict[str, Any]], record: Dict[str, Any]) -> None:
        try:
            queue.put_nowait(record)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover - race
                pass
            try:
                queue.put_nowait(record)
            except asyncio.QueueFull:  # pragma: no cover - still full after drop
                pass

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def backlog(self) -> Iterable[Dict[str, Any]]:
        return tuple(self._backlog)


_GLOBAL_LOG_STREAM = LogStream()


def get_log_stream() -> LogStream:
    """Return the singleton log stream."""

    return _GLOBAL_LOG_STREAM


def stream_processor(stream: LogStream) -> Callable[[Any, str, Dict[str, Any]], Dict[str, Any]]:
    """Return a structlog processor that publishes to ``stream``."""

    def processor(_logger: Any, _method: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        stream.publish(event_dict)
        return event_dict

    return processor


__all__ = ["LogStream", "LogSubscription", "get_log_stream", "stream_processor"]
