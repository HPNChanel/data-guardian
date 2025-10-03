import asyncio
import json
import socket

import pytest

from dg_core.config import AppConfig, IPCConfig, LoggingConfig, NetworkConfig
from dg_core.ipc.server import IPCServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def _rpc(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, method: str, params=None, request_id=1):
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}, "id": request_id})
    writer.write(payload.encode("utf-8") + b"\n")
    await writer.drain()
    response = await reader.readline()
    return json.loads(response.decode("utf-8"))


@pytest.mark.asyncio
async def test_ipc_server_health_and_scan():
    port = _free_port()
    config = AppConfig(
        network=NetworkConfig(),
        logging=LoggingConfig(level="INFO"),
        ipc=IPCConfig(transport="tcp", tcp_host="127.0.0.1", tcp_port=port),
    )
    server = IPCServer(config)
    task = asyncio.create_task(server.serve_forever())
    await asyncio.sleep(0.2)

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    health = await _rpc(reader, writer, "core.health", request_id=1)
    assert health["result"]["status"] == "ok"

    scan = await _rpc(
        reader,
        writer,
        "core.scan",
        params={"text": "email alice@example.com"},
        request_id=2,
    )
    detectors = [item["detector"] for item in scan["result"]["detections"]]
    assert "pii.email" in detectors

    shutdown = await _rpc(reader, writer, "core.shutdown", request_id=3)
    assert shutdown["result"]["status"] == "shutting_down"

    writer.close()
    await writer.wait_closed()
    await asyncio.wait_for(task, timeout=2)


@pytest.mark.asyncio
async def test_policy_only_mode_blocks_mutating_calls() -> None:
    port = _free_port()
    config = AppConfig(
        network=NetworkConfig(policy_only_offline=True),
        logging=LoggingConfig(level="INFO"),
        ipc=IPCConfig(transport="tcp", tcp_host="127.0.0.1", tcp_port=port),
    )
    server = IPCServer(config)
    task = asyncio.create_task(server.serve_forever())
    await asyncio.sleep(0.2)

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    scan = await _rpc(
        reader,
        writer,
        "core.scan",
        params={"text": "email bob@example.com"},
        request_id=1,
    )
    assert scan["error"]["code"] == -32010

    redact = await _rpc(
        reader,
        writer,
        "core.redact",
        params={"text": "secret"},
        request_id=2,
    )
    assert redact["error"]["code"] == -32010

    await _rpc(reader, writer, "core.shutdown", request_id=3)
    writer.close()
    await writer.wait_closed()
    await asyncio.wait_for(task, timeout=2)
