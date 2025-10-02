"""JSON-RPC protocol helpers for the DG Core daemon."""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

IDType = int | str | None


class JSONRPCError(BaseModel):
    """JSON-RPC error payload."""

    code: int
    message: str
    data: Any | None = None

    model_config = ConfigDict(extra="forbid")


class JSONRPCRequest(BaseModel):
    """Incoming JSON-RPC request."""

    jsonrpc: str = Field(default="2.0")
    id: IDType = None
    method: str
    params: Mapping[str, Any] | list[Any] | None = None

    model_config = ConfigDict(extra="forbid")


class JSONRPCResponse(BaseModel):
    """Standard JSON-RPC response payload."""

    jsonrpc: str = Field(default="2.0")
    id: IDType = None
    result: Any | None = None
    error: JSONRPCError | None = None

    model_config = ConfigDict(extra="forbid")


class JSONRPCNotification(BaseModel):
    """JSON-RPC notification payload."""

    jsonrpc: str = Field(default="2.0")
    method: str
    params: Mapping[str, Any] | list[Any] | None = None

    model_config = ConfigDict(extra="forbid")


class ProtocolError(Exception):
    """Raised when a message cannot be parsed."""


class RPCError(Exception):
    """Raised by method handlers to signal JSON-RPC errors."""

    def __init__(self, code: int, message: str, *, data: Any | None = None) -> None:
        super().__init__(message)
        self.error = JSONRPCError(code=code, message=message, data=data)


class MethodNotFound(RPCError):
    def __init__(self, method: str) -> None:
        super().__init__(-32601, "Method not found", data=method)


class InvalidParams(RPCError):
    def __init__(self, message: str, data: Any | None = None) -> None:
        super().__init__(-32602, message, data=data)


@dataclass(slots=True)
class MethodContext:
    """Context passed to registered method handlers."""

    server: Any
    connection: Any


@dataclass(slots=True)
class MethodResult:
    """Result container for method dispatch."""

    result: Any | None = None
    stream: str | None = None


class MethodHandler(Protocol):
    def __call__(self, context: MethodContext, params: Dict[str, Any]) -> Any:  # pragma: no cover - protocol
        ...


class MethodRegistry:
    """Registry for mapping JSON-RPC methods to callables."""

    def __init__(self) -> None:
        self._handlers: Dict[str, MethodHandler] = {}

    def register(self, name: str, handler: MethodHandler) -> None:
        if name in self._handlers:
            raise ValueError(f"Handler already registered for {name}")
        self._handlers[name] = handler

    def method(self, name: str) -> Callable[[MethodHandler], MethodHandler]:
        def decorator(func: MethodHandler) -> MethodHandler:
            self.register(name, func)
            return func

        return decorator

    async def dispatch(self, context: MethodContext, request: JSONRPCRequest) -> MethodResult:
        handler = self._handlers.get(request.method)
        if not handler:
            raise MethodNotFound(request.method)
        params = _coerce_params(request)
        try:
            result = handler(context, params)
            if isinstance(result, MethodResult):
                return result
            if inspect.isawaitable(result):
                awaited = await result  # type: ignore[func-returns-value]
                if isinstance(awaited, MethodResult):
                    return awaited
                return MethodResult(result=awaited)
            return MethodResult(result=result)
        except RPCError:
            raise
        except ValidationError as exc:  # pragma: no cover - defensive
            raise InvalidParams("Invalid parameters", data=exc.errors()) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise RPCError(-32603, "Internal error", data=str(exc)) from exc


def parse_request(payload: str) -> JSONRPCRequest:
    """Parse a JSON string into a :class:`JSONRPCRequest`."""

    try:
        return JSONRPCRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise ProtocolError(str(exc)) from exc


def make_response(request: JSONRPCRequest, result: Any) -> JSONRPCResponse:
    """Create a JSON-RPC success response."""

    return JSONRPCResponse(id=request.id, result=result)


def make_error_response(request: JSONRPCRequest | None, error: JSONRPCError) -> JSONRPCResponse:
    """Create a JSON-RPC error response."""

    return JSONRPCResponse(id=request.id if request else None, error=error)


def _coerce_params(request: JSONRPCRequest) -> Dict[str, Any]:
    params = request.params
    if params is None:
        return {}
    if isinstance(params, Mapping):
        return dict(params)
    if isinstance(params, list):
        if len(params) == 1 and isinstance(params[0], Mapping):
            return dict(params[0])
        raise InvalidParams("Positional parameters are not supported", data=params)
    raise InvalidParams("Parameters must be an object or null", data=params)


__all__ = [
    "IDType",
    "JSONRPCError",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCNotification",
    "MethodContext",
    "MethodRegistry",
    "MethodResult",
    "ProtocolError",
    "RPCError",
    "MethodNotFound",
    "InvalidParams",
    "parse_request",
    "make_response",
    "make_error_response",
]
