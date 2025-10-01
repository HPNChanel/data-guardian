from pathlib import Path

import pytest

pytest.importorskip("yaml")

from dg_core.config import AppConfig
from dg_core.ipc.transport import TCPTransport, UnixSocketTransport, create_transport


def test_default_config_prefers_unix_transport(tmp_path: Path) -> None:
    config = AppConfig()
    config.ipc.socket_path = tmp_path / "dg-core.sock"
    transport = create_transport(config)
    assert isinstance(transport, UnixSocketTransport)
    assert transport.path == tmp_path / "dg-core.sock"


def test_tcp_transport_binds_loopback_only() -> None:
    config = AppConfig()
    config.ipc.transport = "tcp"
    config.ipc.tcp_host = "127.0.0.1"
    config.ipc.tcp_port = 9231
    transport = create_transport(config)
    assert isinstance(transport, TCPTransport)
    assert transport.host == "127.0.0.1"
    assert transport.port == 9231
