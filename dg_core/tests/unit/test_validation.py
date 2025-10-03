from pathlib import Path

import pytest

from dg_core.utils.validation import ensure_loopback_host, resolve_and_check_path


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "::1", "localhost", "LOCALHOST"],
)
def test_ensure_loopback_host_accepts_local(host: str) -> None:
    normalised = ensure_loopback_host(host)
    assert normalised.lower() in {"127.0.0.1", "::1", "localhost"}


@pytest.mark.parametrize("host", ["", "0.0.0.0", "example.com"])
def test_ensure_loopback_host_rejects_remote(host: str) -> None:
    with pytest.raises(ValueError):
        ensure_loopback_host(host)


def test_resolve_and_check_path_rejects_traversal(tmp_path: Path) -> None:
    forbidden = tmp_path / ".." / "secret"
    with pytest.raises(ValueError):
        resolve_and_check_path(forbidden)


def test_resolve_and_check_path_enforces_roots(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed" / "file.txt"
    allowed.parent.mkdir()
    allowed.write_text("ok", encoding="utf-8")
    resolved = resolve_and_check_path(allowed, allowed_roots=[tmp_path])
    assert resolved == allowed.resolve()

    outside = tmp_path.parent / "other.txt"
    outside.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_and_check_path(outside, allowed_roots=[tmp_path])
