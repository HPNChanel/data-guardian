"""Redaction strategies implementation."""
from __future__ import annotations

import base64
from typing import Tuple

from ..models import Detection, RedactionAction, RedactionDecision
from ..utils.checks import mask_value, stable_hash


def apply_strategy(detection: Detection, decision: RedactionDecision) -> str:
    action = decision.action
    if action == RedactionAction.ALLOW:
        return detection.value
    if action == RedactionAction.MASK:
        return _maybe_preserve(mask_value(detection.value), detection.value, decision.preserve_length)
    if action == RedactionAction.HASH:
        hashed = stable_hash(detection.value, salt=decision.salt)
        return _maybe_preserve(hashed, detection.value, decision.preserve_length)
    if action == RedactionAction.REDACT:
        replacement = "[REDACTED]"
        return _maybe_preserve(replacement, detection.value, decision.preserve_length)
    if action == RedactionAction.PSEUDONYMIZE:
        pseudonym = _pseudonym(detection.value, decision.salt)
        return _maybe_preserve(pseudonym, detection.value, decision.preserve_length)
    if action == RedactionAction.DENY:
        raise PermissionError(f"Detection blocked by policy: {detection.detector}")
    return detection.value


def _maybe_preserve(candidate: str, original: str, preserve_length: bool) -> str:
    if not preserve_length:
        return candidate
    if not original:
        return original
    if len(candidate) == len(original):
        return candidate
    repeated = (candidate * ((len(original) // max(len(candidate), 1)) + 1))[: len(original)]
    return repeated


def _pseudonym(value: str, salt: bytes | None) -> str:
    digest = stable_hash(value, salt=salt)
    raw = bytes.fromhex(digest)
    encoded = base64.b32encode(raw).decode("ascii").rstrip("=")
    return encoded[:24]


__all__ = ["apply_strategy"]