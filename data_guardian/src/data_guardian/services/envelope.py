
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from typing import List

FORMAT_VERSION = 3

@dataclass
class RecipientEntry:
    name: str
    key_ct_b64: str
    
@dataclass
class EnvelopeHeader:
    version: int
    alg: str
    keywrap: str
    recipients: List[RecipientEntry]
    chunk_bytes: int = 1024 * 1024  #* 1 MiB default
    
    def to_bytes(self) -> bytes:
        d = asdict(self)
        d["recipients"] = [asdict(r) for r in self.recipients]
        return (json.dumps(d) + "\n").encode("utf-8")
    
    @staticmethod
    def from_bytes(b: bytes) -> "EnvelopeHeader":
        d = json.loads(b.decode("utf-8"))
        d["recipients"] = [RecipientEntry(**r) for r in d["recipients"]]
        return EnvelopeHeader(**d)
