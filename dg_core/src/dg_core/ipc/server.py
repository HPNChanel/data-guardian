"""Async JSON-RPC server over configurable IPC transports."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Type

from pydantic import BaseModel, ValidationError
import structlog

from ..config import AppConfig
from ..policy import PolicyDocument, PolicyEngine, policy_from_path
from ..redactor.engines import RedactionEngine
from ..scanner import Scanner, ScannerConfig, scan_text
from ..utils.text import to_text
from ..version import __version__
from .messages import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    RedactRequest,
    RedactResponse,
    ScanRequest,
    ScanResponse,
)
from .transport import BaseConnection, ConnectionClosed, BaseTransport, create_transport

logger = structlog.get_logger(__name__)


class IPCServer:
    def __init__(self, config: AppConfig, *, default_policy: Path | None = None) -> None:
        self.config = config
        self._transport: BaseTransport = create_transport(config)
        self._shutdown = asyncio.Event()
        self._scanner = Scanner()
        self._default_policy_path = default_policy or (Path(__file__).resolve().parents[2] / "policies" / "default.yaml")
        self._default_policy = policy_from_path(self._default_policy_path)
        self._policy_engine = PolicyEngine(self._default_policy)
        self._redactor = RedactionEngine(self._policy_engine)
        self._handlers: Dict[str, Callable[[JSONRPCRequest], Awaitable[JSONRPCResponse]]] = {
            "core.health": self._handle_health,
            "core.version": self._handle_version,
            "core.scan": self._handle_scan,
            "core.redact": self._handle_redact,
            "core.shutdown": self._handle_shutdown,
        }

    async def serve_forever(self) -> None:
        logger.info("ipc.server.start", transport=self.config.ipc.resolved_transport())
        await self._transport.start(self._handle_connection)
        await self._shutdown.wait()
        await self._transport.close()
        logger.info("ipc.server.stop")

    async def stop(self) -> None:
        self._shutdown.set()

    async def _handle_connection(self, connection: BaseConnection) -> None:
        logger.info("ipc.connection.opened")
        try:
            while not self._shutdown.is_set():
                try:
                    payload = await connection.receive()
                except ConnectionClosed:
                    break
                response = await self._dispatch(payload)
                if response is not None:
                    await connection.send(response)
        finally:
            await connection.close()
            logger.info("ipc.connection.closed")

    async def _dispatch(self, raw: str) -> str | None:
        try:
            request = JSONRPCRequest.model_validate_json(raw)
        except ValidationError as exc:
            logger.error("ipc.parse_error", error=str(exc))
            response = JSONRPCResponse(
                error=JSONRPCError(code=-32700, message="Parse error", data=str(exc)),
                id=None,
            )
            return response.model_dump_json()
        handler = self._handlers.get(request.method)
        if not handler:
            error = JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(code=-32601, message="Method not found", data=request.method),
            )
            return error.model_dump_json()
        try:
            response = await handler(request)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("ipc.handler_error", method=request.method)
            response = JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(code=-32603, message="Internal error", data=str(exc)),
            )
        if request.id is None:
            return None
        response.id = request.id
        return response.model_dump_json()

    async def _handle_health(self, request: JSONRPCRequest) -> JSONRPCResponse:
        payload = {"status": "ok", "version": __version__}
        return JSONRPCResponse(result=payload, id=request.id)

    async def _handle_version(self, request: JSONRPCRequest) -> JSONRPCResponse:
        return JSONRPCResponse(result={"version": __version__}, id=request.id)

    async def _handle_scan(self, request: JSONRPCRequest) -> JSONRPCResponse:
        parsed = self._parse_params(request, ScanRequest)
        if isinstance(parsed, JSONRPCResponse):
            return parsed
        params: ScanRequest = parsed
        config = ScannerConfig(
            enabled=params.detectors,
            max_detections=params.max_results,
        )
        detections = scan_text(params.text, scanner=self._scanner, config=config)
        payload = ScanResponse(detections=[asdict(det) for det in detections])
        return JSONRPCResponse(result=json.loads(payload.model_dump_json()), id=request.id)

    async def _handle_redact(self, request: JSONRPCRequest) -> JSONRPCResponse:
        parsed = self._parse_params(request, RedactRequest)
        if isinstance(parsed, JSONRPCResponse):
            return parsed
        params: RedactRequest = parsed
        policy_doc = self._default_policy
        if params.policy_path:
            policy_doc = policy_from_path(Path(params.policy_path))
        elif params.policy:
            policy_doc = PolicyDocument.model_validate(params.policy)
        engine = PolicyEngine(policy_doc)
        redactor = RedactionEngine(engine)
        detections = scan_text(params.text, scanner=self._scanner)
        redacted, segments = redactor.redact(params.text, detections)
        response = RedactResponse(
            text=to_text(redacted),
            segments=[asdict(segment) for segment in segments],
        )
        return JSONRPCResponse(result=json.loads(response.model_dump_json()), id=request.id)

    async def _handle_shutdown(self, request: JSONRPCRequest) -> JSONRPCResponse:
        await self.stop()
        return JSONRPCResponse(result={"status": "shutting_down"}, id=request.id)

    def _parse_params(self, request: JSONRPCRequest, model: Type[BaseModel]) -> BaseModel | JSONRPCResponse:
        if request.params is None:
            payload: Dict[str, Any] = {}
        elif isinstance(request.params, list):
            payload = request.params[0] if request.params else {}
        else:
            payload = request.params
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(code=-32602, message="Invalid params", data=exc.errors()),
            )


__all__ = ["IPCServer"]