# Define dataclasses or typed models (e.g., KeyInfo, DgdHeader).

from __future__ import annotations
from dataclasses import dataclass, field

from typing import Optional

@dataclass(slots=True)
class KeyInfo:
    """Metadata for a stored key entry"""
    kid: str
    alg: str
    label: str = ""
    created_at: int = 0
    last_used: Optional[int] = None
    expiry: Optional[int] = None
    
from .storage.header import FileHeader as DgdHeader
from .storage.header import Recipient

__all__ = ["KeyInfo", "Recipient", "DgdHeader"]  
