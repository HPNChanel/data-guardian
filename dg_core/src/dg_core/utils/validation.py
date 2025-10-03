"""Validation helpers for security-sensitive inputs."""
from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Iterable, Sequence

_LOCAL_HOST_ALIASES = {"localhost"}


def ensure_loopback_host(host: str) -> str:
    """Ensure the provided host string resolves to a loopback address.

    Parameters
    ----------
    host:
        Hostname or IP address to validate.

    Returns
    -------
    str
        Normalised host value (hostname lower-cased, IP unchanged).

    Raises
    ------
    ValueError
        If ``host`` does not refer to a loopback interface.
    """

    host = host.strip()
    if not host:
        raise ValueError("Host must not be empty")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        alias = host.lower()
        if alias in _LOCAL_HOST_ALIASES:
            return alias
        raise ValueError(f"Host '{host}' must resolve to localhost or loopback") from None
    if not address.is_loopback:
        raise ValueError(f"Host '{host}' must be a loopback address")
    return host


def _normalise_path(path: Path | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_and_check_path(
    path: Path | str,
    *,
    allowed_roots: Sequence[Path] | None = None,
    must_exist: bool = False,
    require_file: bool | None = None,
) -> Path:
    """Resolve ``path`` safely and enforce optional constraints.

    The function expands user tildes, resolves symlinks for existing parents, and
    rejects relative paths containing ``..`` components to prevent directory
    traversal. When ``allowed_roots`` is supplied, the resolved path must reside
    within one of the permitted roots.
    """

    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        if any(part == ".." for part in candidate.parts):
            raise ValueError(f"Path traversal is not allowed: {path}")
        resolved = _normalise_path(Path.cwd() / candidate)
    else:
        resolved = _normalise_path(candidate)

    if allowed_roots:
        normalised_roots = [_normalise_path(root) for root in allowed_roots]
        if not any(_is_relative_to(resolved, root) for root in normalised_roots):
            roots_display = ", ".join(str(root) for root in normalised_roots)
            raise ValueError(f"Path '{resolved}' is outside permitted locations: {roots_display}")

    if must_exist and not resolved.exists():
        raise ValueError(f"Path does not exist: {resolved}")

    if require_file is True and resolved.exists() and not resolved.is_file():
        raise ValueError(f"Expected file path but found directory: {resolved}")
    if require_file is False and resolved.exists() and not resolved.is_dir():
        raise ValueError(f"Expected directory path but found file: {resolved}")

    return resolved


__all__ = ["ensure_loopback_host", "resolve_and_check_path"]
