"""IPC transport abstractions."""
from __future__ import annotations

import asyncio
import os
import sys
from abc import ABC, abstractmethod
from asyncio import StreamReader, StreamWriter
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from typing import Awaitable, Callable, Optional, Set

from ..config import AppConfig
from ..paths import runtime_config_dir
from ..utils.validation import ensure_loopback_host, resolve_and_check_path

MessageHandler = Callable[["BaseConnection"], Awaitable[None]]


class ConnectionClosed(RuntimeError):
    """Raised when a connection is closed unexpectedly."""


class BaseConnection(ABC):
    @abstractmethod
    async def receive(self) -> str:  # pragma: no cover - interface
        ...

    @abstractmethod
    async def send(self, payload: str) -> None:  # pragma: no cover - interface
        ...

    @abstractmethod
    async def close(self) -> None:  # pragma: no cover - interface
        ...


@dataclass(eq=False)
class SocketConnection(BaseConnection):
    reader: StreamReader
    writer: StreamWriter

    async def receive(self) -> str:
        data = await self.reader.readline()
        if not data:
            raise ConnectionClosed("socket closed")
        return data.decode("utf-8").rstrip("\r\n")

    async def send(self, payload: str) -> None:
        message = payload.encode("utf-8") + b"\n"
        self.writer.write(message)
        await self.writer.drain()

    async def close(self) -> None:
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except ConnectionResetError:  # pragma: no cover - race condition
            pass


class BaseTransport(ABC):
    def __init__(self) -> None:
        self._clients: Set[BaseConnection] = set()

    @abstractmethod
    async def start(self, handler: MessageHandler) -> None:  # pragma: no cover - interface
        ...

    @abstractmethod
    async def close(self) -> None:  # pragma: no cover - interface
        ...

    async def broadcast(self, payload: str) -> None:
        await asyncio.gather(*(client.send(payload) for client in list(self._clients)), return_exceptions=True)


class _SocketTransport(BaseTransport):
    def __init__(self) -> None:
        super().__init__()
        self._server: asyncio.base_events.Server | None = None

    async def _serve(self, handler: MessageHandler, create_server: Callable[..., Awaitable[asyncio.base_events.Server]], *args, **kwargs) -> None:
        async def _client_connected(reader: StreamReader, writer: StreamWriter) -> None:
            connection = SocketConnection(reader=reader, writer=writer)
            self._clients.add(connection)
            try:
                await handler(connection)
            finally:
                self._clients.discard(connection)
                await connection.close()

        self._server = await create_server(_client_connected, *args, **kwargs)

    async def close(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for client in list(self._clients):
            await client.close()
        self._clients.clear()


class UnixSocketTransport(_SocketTransport):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    async def start(self, handler: MessageHandler) -> None:
        if self.path.exists():
            self.path.unlink()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        await self._serve(handler, asyncio.start_unix_server, path=str(self.path))

    async def close(self) -> None:
        await super().close()
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError:
            pass


class TCPTransport(_SocketTransport):
    def __init__(self, host: str, port: int) -> None:
        super().__init__()
        self.host = ensure_loopback_host(host)
        self.port = port

    async def start(self, handler: MessageHandler) -> None:
        await self._serve(handler, asyncio.start_server, host=self.host, port=self.port)


class NamedPipeTransport(BaseTransport):
    """Windows named pipe transport using pywin32 in a background thread."""

    def __init__(self, pipe_name: str) -> None:
        if sys.platform != "win32":  # pragma: no cover - platform guard
            raise RuntimeError("Named pipes only supported on Windows")
        super().__init__()
        self.pipe_name = pipe_name
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tasks: Set[asyncio.Future] = set()

    async def start(self, handler: MessageHandler) -> None:
        import win32file
        import win32pipe

        loop = asyncio.get_running_loop()
        self._loop = loop
        pipe_path = self.pipe_name if self.pipe_name.startswith("\\\\.\\pipe\\") else f"\\\\.\\pipe\\{self.pipe_name}"

        def _run() -> None:
            while not self._stop_event.is_set():
                handle = win32pipe.CreateNamedPipe(
                    pipe_path,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    1024 * 64,
                    1024 * 64,
                    0,
                    None,
                )
                try:
                    win32pipe.ConnectNamedPipe(handle, None)
                except OSError:
                    win32file.CloseHandle(handle)
                    if self._stop_event.is_set():
                        break
                    continue
                future = asyncio.run_coroutine_threadsafe(
                    self._handle_client(handle, handler), loop
                )
                self._tasks.add(future)

        self._thread = Thread(target=_run, name="dg-core-pipe", daemon=True)
        self._thread.start()

    async def _handle_client(self, handle: int, handler: MessageHandler) -> None:
        import win32file
        import win32pipe

        connection = PipeConnection(handle)
        self._clients.add(connection)
        try:
            await handler(connection)
        finally:
            self._clients.discard(connection)
            await connection.close()
            try:
                win32pipe.DisconnectNamedPipe(handle)
            except OSError:
                pass
            win32file.CloseHandle(handle)

    async def close(self) -> None:
        if self._thread:
            self._stop_event.set()
            pipe_path = self.pipe_name if self.pipe_name.startswith("\\\\.\\pipe\\") else f"\\\\.\\pipe\\{self.pipe_name}"
            await _touch_pipe(pipe_path)
            self._thread.join(timeout=1)
        for future in list(self._tasks):
            future.cancel()
        for client in list(self._clients):
            await client.close()
        self._clients.clear()


class PipeConnection(BaseConnection):
    """Async wrapper around a Windows named pipe handle."""

    def __init__(self, handle: int) -> None:
        import win32file

        self._handle = handle
        self._buffer = b""
        self._closed = False
        self._win32file = win32file

    async def receive(self) -> str:
        loop = asyncio.get_running_loop()
        while b"\n" not in self._buffer:
            chunk = await loop.run_in_executor(None, self._read_chunk)
            if not chunk:
                self._closed = True
                raise ConnectionClosed("pipe closed")
            self._buffer += chunk
        line, self._buffer = self._buffer.split(b"\n", 1)
        return line.decode("utf-8").rstrip("\r")

    async def send(self, payload: str) -> None:
        data = payload.encode("utf-8") + b"\n"
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._write_chunk, data)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._win32file.CloseHandle(self._handle)
        except Exception:  # pragma: no cover - best effort
            pass

    def _read_chunk(self) -> bytes:
        _, data = self._win32file.ReadFile(self._handle, 4096)
        return data

    def _write_chunk(self, data: bytes) -> None:
        self._win32file.WriteFile(self._handle, data)


async def _touch_pipe(path: str) -> None:
    if sys.platform != "win32":  # pragma: no cover
        return
    import win32file
    import win32pipe

    loop = asyncio.get_running_loop()

    def _connect() -> None:
        try:
            handle = win32file.CreateFile(
                path,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
            win32file.CloseHandle(handle)
        except Exception:
            pass

    await loop.run_in_executor(None, _connect)


def create_transport(config: AppConfig) -> BaseTransport:
    ipc_config = config.ipc
    transport = ipc_config.resolved_transport()
    if transport == "uds":
        if ipc_config.socket_path is not None:
            socket_path = resolve_and_check_path(ipc_config.socket_path)
        else:
            default_runtime = runtime_config_dir() / "ipc" / "dg-core.sock"
            socket_path = resolve_and_check_path(default_runtime)
        return UnixSocketTransport(Path(socket_path))
    if transport == "pipe":
        pipe_name = ipc_config.named_pipe or "dg_core"
        return NamedPipeTransport(pipe_name)
    if transport == "tcp":
        host = getattr(ipc_config, "tcp_host", "127.0.0.1")
        port = ipc_config.tcp_port or 8765
        return TCPTransport(host, port)
    raise ValueError(f"Unknown transport: {transport}")


__all__ = [
    "BaseTransport",
    "SocketConnection",
    "NamedPipeTransport",
    "UnixSocketTransport",
    "TCPTransport",
    "create_transport",
    "BaseConnection",
    "ConnectionClosed",
]