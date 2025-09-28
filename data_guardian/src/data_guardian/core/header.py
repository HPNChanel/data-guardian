
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator

from data_guardian.core.exceptions import CryptoError, DataGuardianError

HEADER_MAGIC = "DGAR"
HEADER_VERSION = 1


class RecipientHeader(BaseModel):
    recipient_id: str
    key_wrapping_alg: str
    encrypted_key: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Header(BaseModel):
    magic: str = Field(default=HEADER_MAGIC)
    version: int = Field(default=HEADER_VERSION)
    algorithm_suite: str
    recipients: list[RecipientHeader]
    salt: str
    chunk_size: int
    aad_digest: str  #* base64 SHA-256 digest of external AAD
    created_at: datetime
    policy_id: str | None = None
    additional_meta: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {"frozen": True}
    
    @model_validator(mode="after")
    def _validate(self) -> "Header":
        if self.magic != HEADER_MAGIC:
            raise DataGuardianError("Header magic mismatch")
        if self.version != HEADER_VERSION:
            raise DataGuardianError("Unsupported header version")
        if self.chunk_size <= 0 or self.chunk_size % 4096:
            raise DataGuardianError("Chunk size must be positive and 4 KiB aligned")
        return self
    
    @property
    def salt_bytes(self) -> bytes:
        try:
            return base64.b64decode(self.salt, validate=True)
        except ValueError as exc:
            raise DataGuardianError("Header salt is not valid base64") from exc
    
    @property
    def aad_digest_bytes(self) -> bytes:
        try:
            return base64.b64decode(self.aad_digest, validate=True)
        except ValueError as exc:
            raise DataGuardianError("Header aad_digest is not valid base64") from exc
    
    def aad_domain(self) -> bytes:
        payload = json.dumps(
            {
                "magic": self.magic,
                "version": self.version,
                "algorithm_suite": self.algorithm_suite,
                "nonce_policy": self.nonce_policy,
                "created_at": self.created_at.isoformat(),
                "policy_id": self.policy_id or "",
            },
            sort_keys=True,
            separators=(",",":"),
        )
        return payload.encode("utf-8")
    
    def chunk_aad(self, chunk_index: int) -> bytes:
        if chunk_index < 0:
            raise CryptoError("Chunk index must be non-negative")
        digest_input = chunk_index.to_bytes(8, "big")
        return self.aad_digest_bytes + digest_input
    
    def to_bytes(self) -> bytes:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True).encode("utf-8")
    
    @classmethod
    def from_bytes(cls, payload: bytes) -> "Header":
        try:
            data = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise DataGuardianError("Header JSON is invalid") from exc
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            raise DataGuardianError("Header validation failed") from exc
        
    @staticmethod
    def compute_aad_digest(aad: bytes) -> str:
        import hashlib
        
        digest = hashlib.sha256(aad).digest()
        return base64.b64encode(digest).decode("ascii")
    
    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(tz=timezone.utc)
    