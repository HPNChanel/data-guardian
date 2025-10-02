import asyncio
import json

import pytest

from dg_core.daemon.protocol import (
    JSONRPCError,
    JSONRPCRequest,
    MethodContext,
    MethodRegistry,
    MethodResult,
    ProtocolError,
    RPCError,
    make_error_response,
    make_response,
    parse_request,
)


def test_parse_request_roundtrip() -> None:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "core.ping", "params": {}})
    request = parse_request(payload)
    assert request.method == "core.ping"
    assert request.id == 1
    response = make_response(request, {"ok": True})
    assert response.model_dump() == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"ok": True},
        "error": None,
    }


def test_parse_request_invalid_json() -> None:
    with pytest.raises(ProtocolError):
        parse_request("not json")


def test_method_registry_dispatch_sync() -> None:
    registry = MethodRegistry()

    @registry.method("core.ping")
    def handler(context: MethodContext, params: dict[str, object]) -> dict[str, object]:
        assert context.server == "server"
        assert context.connection == "connection"
        return {"pong": True}

    request = JSONRPCRequest(method="core.ping", id=5)
    result = asyncio.run(
        registry.dispatch(MethodContext(server="server", connection="connection"), request)
    )
    assert isinstance(result, MethodResult)
    assert result.result == {"pong": True}


def test_method_registry_dispatch_async() -> None:
    registry = MethodRegistry()

    @registry.method("core.async")
    async def handler(_context: MethodContext, params: dict[str, object]) -> dict[str, object]:
        await asyncio.sleep(0)
        return {"echo": params["value"]}

    request = JSONRPCRequest(method="core.async", params={"value": 42}, id=7)
    result = asyncio.run(registry.dispatch(MethodContext(server=None, connection=None), request))
    assert isinstance(result, MethodResult)
    assert result.result == {"echo": 42}


def test_method_registry_unknown_method() -> None:
    registry = MethodRegistry()
    request = JSONRPCRequest(method="missing", id=10)
    with pytest.raises(RPCError) as excinfo:
        asyncio.run(registry.dispatch(MethodContext(server=None, connection=None), request))
    assert excinfo.value.error.code == -32601


def test_make_error_response() -> None:
    request = JSONRPCRequest(method="core.fail", id=99)
    error = JSONRPCError(code=-32000, message="boom")
    response = make_error_response(request, error)
    assert response.error == error
    assert response.id == 99


def test_method_registry_duplicate_registration() -> None:
    registry = MethodRegistry()

    def handler(_context: MethodContext, _params: dict[str, object]) -> dict[str, object]:
        return {"ok": True}

    registry.register("core.ping", handler)
    with pytest.raises(ValueError):
        registry.register("core.ping", handler)
