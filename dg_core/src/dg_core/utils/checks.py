"""Utility validation helpers."""
from __future__ import annotations

import hashlib
from typing import Iterable


def luhn_valid(value: str) -> bool:
    digits = [int(char) for char in value if char.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def stable_hash(value: str, *, salt: bytes | None = None) -> str:
    digest = hashlib.sha256()
    if salt:
        digest.update(salt)
    digest.update(value.encode("utf-8", errors="ignore"))
    return digest.hexdigest()


def mask_value(value: str, mask_char: str = "*") -> str:
    if not value:
        return value
    return mask_char * len(value)


def sliding_window(text: str, window: int) -> Iterable[str]:
    for index in range(0, len(text), window):
        yield text[index : index + window]
