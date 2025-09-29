"""Shared domain models used across DG Core."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


@dataclass(slots=True)
class Span:
    start: int
    end: int

    def length(self) -> int:
        return self.end - self.start


@dataclass(slots=True)
class Detection:
    detector: str
    span: Span
    value: str
    context_before: str
    context_after: str
    confidence: float = 1.0
    categories: Tuple[str, ...] = ()


class RedactionAction(str, Enum):
    MASK = "MASK"
    HASH = "HASH"
    REDACT = "REDACT"
    PSEUDONYMIZE = "PSEUDONYMIZE"
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(slots=True)
class RedactionDecision:
    action: RedactionAction
    reason: str
    preserve_length: bool
    salt: Optional[bytes] = None


@dataclass(slots=True)
class RedactedSegment:
    span: Span
    replacement: str
    action: RedactionAction

