"""Async daemon server exposing DG Core functionality."""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable

import structlog

from pydantic import ValidationError

from ..policy import PolicyDocument, PolicyEngine, policy_from_path
from ..redactor.engines import RedactionEngine
from ..scanner import Scanner, ScannerConfig, scan_text
from ..utils.text import to_text
from ..utils.validation import resolve_and_check_path
from ..version import __version__
from ..ipc.transport import BaseConnection, ConnectionClosed, NamedPipeTransport, UnixSocketTransport
from ..logging import configure_logging
from ..paths import default_named_pipe, default_unix_socket_path, runtime_config_dir
from .log_stream import get_log_stream
from .protocol import (
    JSONRPCError,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    InvalidParams,
    MethodContext,
    MethodRegistry,
    MethodResult,
    ProtocolError,
    RPCError,
    make_error_response,
    make_response,
    parse_request,
)

_MAX_REQUEST_BYTES = 512 * 1024
_REQUEST_TIMEOUT = 15.0
_LOG_STREAM_NAME = "logs"
_DEFAULT_PIPE = default_named_pipe()
_DEFAULT_SOCKET = default_unix_socket_path()

logger = structlog.get_logger(__name__)


class DaemonServer:
    """JSON-RPC daemon orchestrating DG Core business logic."""

    def __init__(
        self,
        *,
        socket_path: Path | None = None,
        pipe_name: str | None = None,
        max_request_bytes: int = _MAX_REQUEST_BYTES,
        request_timeout: float = _REQUEST_TIMEOUT,
    ) -> None:
        self._max_request_bytes = max_request_bytes
        self._request_timeout = request_timeout
        self._shutdown = asyncio.Event()
        self._log_stream = get_log_stream()
        self._scanner = Scanner()
        self._default_policy_path = (
            Path(__file__).resolve().parents[2] / "policies" / "default.yaml"
        )
        self._default_policy = policy_from_path(self._default_policy_path)
        self._policy_engine = PolicyEngine(self._default_policy)
        self._redactor = RedactionEngine(self._policy_engine)
        self._registry = MethodRegistry()
        self._start_time = time.monotonic()
        self._request_count = 0
        self._connections: set[int] = set()
        self._transport = self._create_transport(socket_path=socket_path, pipe_name=pipe_name)
        self._policy_roots = [
            self._default_policy_path.parent,
            runtime_config_dir(),
            Path.cwd(),
        ]
        self._register_methods()

    async def serve_forever(self) -> None:
        loop = asyncio.get_running_loop()
        self._log_stream.attach_loop(loop)
        endpoint = self.endpoint
        logger.info("daemon.start", endpoint=str(endpoint))
        await self._transport.start(self._handle_connection)
        await self._shutdown.wait()
        await self._transport.close()
        logger.info("daemon.stop")

    async def stop(self) -> None:
        self._shutdown.set()

    @property
    def endpoint(self) -> Path | str:
        if isinstance(self._transport, UnixSocketTransport):
            return self._transport.path
        if isinstance(self._transport, NamedPipeTransport):
            return self._transport.pipe_name
        return "unknown"

    def _create_transport(
        self, *, socket_path: Path | None, pipe_name: str | None
    ) -> NamedPipeTransport | UnixSocketTransport:
        if sys.platform == "win32":
            name = pipe_name or _DEFAULT_PIPE
            return NamedPipeTransport(name)
        path = Path(socket_path or _DEFAULT_SOCKET)
        path.parent.mkdir(parents=True, exist_ok=True)
        return UnixSocketTransport(path)

    async def _handle_connection(self, connection: BaseConnection) -> None:
        conn_id = id(connection)
        self._connections.add(conn_id)
        logger.info("daemon.connection.opened", connection=conn_id)
        tasks: set[asyncio.Task[Any]] = set()
        subscriptions: list[Any] = []
        try:
            while not self._shutdown.is_set():
                try:
                    payload = await asyncio.wait_for(
                        connection.receive(), timeout=self._request_timeout
                    )
                except asyncio.TimeoutError:
                    timeout = JSONRPCResponse(
                        error=JSONRPCError(code=-32000, message="Request timed out"),
                        id=None,
                    )
                    await connection.send(timeout.model_dump_json())
                    continue
                except ConnectionClosed:
                    break

                if not payload:
                    continue
                if len(payload.encode("utf-8")) > self._max_request_bytes:
                    error = JSONRPCResponse(
                        error=JSONRPCError(
                            code=-32600,
                            message="Request too large",
                            data=len(payload),
                        ),
                        id=None,
                    )
                    await connection.send(error.model_dump_json())
                    continue

                response_payload = await self._dispatch_request(
                    connection, payload, tasks, subscriptions
                )
                if response_payload is not None:
                    await connection.send(response_payload)
        finally:
            for task in tasks:
                task.cancel()
            for subscription in subscriptions:
                try:
                    await subscription.aclose()
                except Exception:  # pragma: no cover - defensive cleanup
                    pass
            await connection.close()
            self._connections.discard(conn_id)
            logger.info("daemon.connection.closed", connection=conn_id)

    async def _dispatch_request(
        self,
        connection: BaseConnection,
        payload: str,
        tasks: set[asyncio.Task[Any]],
        subscriptions: list[Any],
    ) -> str | None:
        request: JSONRPCRequest | None = None
        try:
            request = parse_request(payload)
        except ProtocolError as exc:
            error = JSONRPCError(code=-32700, message="Parse error", data=str(exc))
            return JSONRPCResponse(id=None, error=error).model_dump_json()

        context = MethodContext(server=self, connection=connection)
        try:
            result = await self._registry.dispatch(context, request)
        except RPCError as exc:
            response = make_error_response(request, exc.error)
            return response.model_dump_json()

        if result.stream:
            await self._attach_stream(result.stream, connection, tasks, subscriptions)

        if request.id is None:
            return None
        response = make_response(request, result.result)
        self._request_count += 1
        return response.model_dump_json()

    async def _attach_stream(
        self,
        stream_name: str,
        connection: BaseConnection,
        tasks: set[asyncio.Task[Any]],
        subscriptions: list[Any],
    ) -> None:
        if stream_name != _LOG_STREAM_NAME:
            raise RPCError(-32603, f"Unknown stream: {stream_name}")
        subscription = self._log_stream.subscribe()
        subscriptions.append(subscription)
        task = asyncio.create_task(self._pump_logs(connection, subscription))
        tasks.add(task)

    async def _pump_logs(self, connection: BaseConnection, subscription: Any) -> None:
        try:
            async for record in subscription:
                notification = JSONRPCNotification(method="core.log", params=record)
                try:
                    await connection.send(notification.model_dump_json())
                except ConnectionClosed:
                    break
        except asyncio.CancelledError:  # pragma: no cover - cancellation path
            pass
        finally:
            try:
                await subscription.aclose()
            except Exception:  # pragma: no cover - defensive
                pass

    # -- Method handlers -------------------------------------------------

    def _register_methods(self) -> None:
        registry = self._registry

        @registry.method("core.ping")
        async def _ping(_ctx: MethodContext, _params: Dict[str, Any]) -> Dict[str, Any]:
            return {"ok": True, "version": __version__}

        @registry.method("core.scan_path")
        async def _scan_path(_ctx: MethodContext, params: Dict[str, Any]) -> Dict[str, Any]:
            path = self._require_path(params, "path")
            detectors = params.get("detectors")
            max_results = params.get("max_results")
            data = await asyncio.to_thread(path.read_bytes)
            config = ScannerConfig(
                enabled=detectors,
                max_detections=max_results,
            )
            detections = await asyncio.to_thread(
                scan_text, data, scanner=self._scanner, config=config
            )
            return {
                "path": str(path),
                "detections": [asdict(det) for det in detections],
            }

        @registry.method("core.redact_file")
        async def _redact_file(_ctx: MethodContext, params: Dict[str, Any]) -> Dict[str, Any]:
            path = self._require_path(params, "path")
            output_path = params.get("output_path")
            policy_payload = params.get("policy")
            policy_path_value = params.get("policy_path")

            if policy_payload and policy_path_value:
                raise InvalidParams("Specify either policy or policy_path, not both")

            document = await asyncio.to_thread(
                self._resolve_policy, policy_payload, policy_path_value
            )
            engine = self._policy_engine if document is self._default_policy else PolicyEngine(document)
            redactor = self._redactor if document is self._default_policy else RedactionEngine(engine)
            content = await asyncio.to_thread(path.read_bytes)
            detections = await asyncio.to_thread(scan_text, content, scanner=self._scanner)
            redacted, segments = await asyncio.to_thread(
                redactor.redact, content, detections
            )
            rendered = to_text(redacted)
            written_to: str | None = None
            if output_path:
                target = self._require_output_path(output_path)
                await asyncio.to_thread(self._write_output, target, redacted)
                written_to = str(target)

            return {
                "path": str(path),
                "output": rendered,
                "segments": [asdict(segment) for segment in segments],
                "written_to": written_to,
            }

        @registry.method("core.load_policy")
        async def _load_policy(_ctx: MethodContext, params: Dict[str, Any]) -> Dict[str, Any]:
            path = self._require_path(params, "path")
            document = await asyncio.to_thread(policy_from_path, path)
            return {"path": str(path), "policy": document.model_dump(mode="json")}

        @registry.method("core.test_policy")
        async def _test_policy(_ctx: MethodContext, params: Dict[str, Any]) -> Dict[str, Any]:
            sample = params.get("text")
            if not isinstance(sample, (str, bytes)):
                raise InvalidParams("text must be a string")
            policy_payload = params.get("policy")
            policy_path_value = params.get("policy_path")
            document = await asyncio.to_thread(
                self._resolve_policy, policy_payload, policy_path_value
            )
            engine = self._policy_engine if document is self._default_policy else PolicyEngine(document)
            redactor = self._redactor if document is self._default_policy else RedactionEngine(engine)
            detections = await asyncio.to_thread(scan_text, sample, scanner=self._scanner)
            decisions = [
                {
                    "detector": det.detector,
                    "action": decision.action.value,
                    "reason": decision.reason,
                }
                for det, decision in (
                    (det, engine.decision_for(det)) for det in detections
                )
            ]
            redacted, _segments = await asyncio.to_thread(redactor.redact, sample, detections)
            return {
                "detections": [asdict(det) for det in detections],
                "decisions": decisions,
                "output": to_text(redacted),
            }

        @registry.method("core.get_status")
        async def _get_status(_ctx: MethodContext, _params: Dict[str, Any]) -> Dict[str, Any]:
            uptime = time.monotonic() - self._start_time
            return {
                "ok": True,
                "uptime": uptime,
                "requests": self._request_count,
                "connections": len(self._connections),
                "log_subscribers": self._log_stream.subscriber_count,
            }

        @registry.method("core.tail_logs")
        async def _tail_logs(_ctx: MethodContext, _params: Dict[str, Any]) -> MethodResult:
            return MethodResult(result={"subscribed": True}, stream=_LOG_STREAM_NAME)

    # -- Helpers ---------------------------------------------------------

    def _require_path(self, params: Dict[str, Any], key: str) -> Path:
        raw = params.get(key)
        if not isinstance(raw, str):
            raise InvalidParams(f"'{key}' must be a string path")
        try:
            return resolve_and_check_path(raw, must_exist=True, require_file=True)
        except ValueError as exc:
            raise RPCError(-32001, str(exc)) from exc

    def _require_output_path(self, raw: str) -> Path:
        resolved = resolve_and_check_path(raw, must_exist=False)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def _resolve_policy(
        self, inline: Dict[str, Any] | None, policy_path: str | None
    ) -> PolicyDocument:
        if inline is not None:
            try:
                return PolicyDocument.model_validate(inline)
            except ValidationError as exc:
                raise InvalidParams("Invalid policy document", data=exc.errors()) from exc
        if policy_path:
            try:
                candidate = resolve_and_check_path(
                    policy_path,
                    allowed_roots=self._policy_roots,
                    must_exist=True,
                    require_file=True,
                )
            except ValueError as exc:
                raise RPCError(-32001, str(exc)) from exc
            try:
                return policy_from_path(candidate)
            except ValidationError as exc:
                raise InvalidParams("Invalid policy document", data=exc.errors()) from exc
        return self._default_policy

    def _write_output(self, path: Path, content: str | bytes) -> None:
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")


async def _async_main(args: argparse.Namespace) -> None:
    configure_logging()
    server = DaemonServer(socket_path=args.socket, pipe_name=args.pipe)
    try:
        await server.serve_forever()
    except asyncio.CancelledError:  # pragma: no cover - cancellation path
        pass


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the DG Core daemon")
    parser.add_argument("--socket", type=Path, default=None, help="Override the Unix socket path")
    parser.add_argument("--pipe", type=str, default=None, help="Override the Windows named pipe")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
