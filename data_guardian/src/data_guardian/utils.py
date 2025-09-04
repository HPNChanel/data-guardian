from __future__ import annotations

import base64

# Re-export sha256_file for convenience
from .crypto.hasher import sha256_file  # noqa: F401


def b64e(b: bytes) -> str:
    """URL-safe base64 encoding without padding."""
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def b64d(s: str) -> bytes:
    """URL-safe base64 decode, accepting missing padding."""
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))

