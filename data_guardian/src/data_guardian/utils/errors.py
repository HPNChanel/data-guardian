
from __future__ import annotations

import secrets
from typing import Any


class AppError(Exception):
    """Base exception for Data Guardian"""


class KeyNotFound(AppError):
    """Raised when a key identifier cannot be resolved"""


class InvalidPassphrase(AppError):
    """Raised when decrypting a private key fails due to passphrase mismatch"""


class InvalidHeader(AppError):
    """Raised when the envelope header is missing or malformed"""


class InvalidCiphertext(AppError):
    """Raised when ciphertext authentication fails"""
    

def constant_time_compare(lhs: bytes | str, rhs: bytes | str) -> bool:
    """Compare two byte sequences without leaking timing information"""
    if isinstance(lhs, str):
        lhs = lhs.encode("utf-8")
    if isinstance(rhs, str):
        rhs = rhs.encode("utf-8")
    
    try:
        return secrets.compare_digest(lhs, rhs)
    except Exception:
        return False


__all__ = [
    "AppError",
    "KeyNotFound",
    "InvalidPassphrase",
    "InvalidHeader",
    "InvalidCiphertext",
    "constant_time_compare",
]
