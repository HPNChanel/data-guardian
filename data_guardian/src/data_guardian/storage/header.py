
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from ..utils import b64d
from ..utils.errors import InvalidHeader


HEADER_VERSION = "1"
SUPPORTED_AEAD = {"AESGCM", "CHACHA20"}
SUPPORTED_ENC = {"RSA-OAEP", "X25519-KEM"}


@dataclass(slots=True)
class Recipient:
    kid: str
    scheme: str
    enc_key: str
    ephemeral_public: Optional[str] = None
    nonce: Optional[str] = None
    share_index: Optional[int] = None
    
    def validate(self) -> None:
        if self.scheme not in SUPPORTED_ENC:
            raise InvalidHeader(f"Unsupported key wrap scheme: {self.scheme}")
        if not self.enc_key:
            raise InvalidHeader(f"Recipient missing wrapped key material")
        if self.scheme == "X25519-KEM":
            if not self.ephemeral_public or not self.nonce:
                raise InvalidHeader("X25519 recipient missing metadata")
        else:
            if self.ephemeral_public or self.nonce:
                raise InvalidHeader("RSA recipient should not carry X25519 metadata")
            
    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "kid": self.kid,
            "scheme": self.scheme,
            "ek": self.enc_key,
        }
        
        if self.ephemeral_public:
            data["epk"] = self.ephemeral_public
        if self.nonce:
            data["nonce"] = self.nonce
        if self.share_index is not None:
            data["share_index"] = self.share_index
        return data
    
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Recipient":
        kid = payload.get("kid")
        if not kid:
            raise InvalidHeader("Recipient missing kid")
        scheme = (payload.get("scheme") or "RSA-OAEP").upper()
        enc_key = payload.get("ek") or payload.get("ek_b64")
        if not enc_key:
            raise InvalidHeader("Recipient missing wrapped key")
        return cls(
            kid = kid,
            scheme=scheme,
            enc_key=enc_key,
            ephemeral_public=payload.get("epk") or payload.get("epk_pem_b64"),
            nonce=payload.get("nonce") or payload.get("nonce_b64"),
            share_index=payload.get("share_index"),
        )


@dataclass(slots=True)
class FileHeader:
    version: str = HEADER_VERSION
    aead: str = "AESGCM"
    enc: str = "RSA-OAEP"
    nonce: str = ""
    recipients: List[Recipient] = field(default_factory=list)
    created_at: int = field(default_factory=lambda: int(time.time()))
    chunked: bool = True
    chunk_size: Optional[int] = None
    total_size: Optional[int] = None
    threshold: Optional[int] = None
    aad_tag: Optional[str] = None
    kdf: Optional[Dict[str, Any]] = None
    salt: Optional[str] = None
    
    def validate(self) -> None:
        if not self.version:
            raise InvalidHeader("Missing header version")
        
        if self.version != HEADER_VERSION:
            raise InvalidHeader(f"Unsupported header version: {self.version}")
        
        if self.aead not in SUPPORTED_AEAD:
            raise InvalidHeader(f"Unsupported AEAD: {self.aead}")
        
        if self.enc not in SUPPORTED_ENC:
            raise InvalidHeader(f"Unsupported key wrap: {self.enc}")
        
        if not self.nonce:
            raise InvalidHeader("Missing content nonce")
        
        if not self.recipients:
            raise InvalidHeader("Header contains no recipients")
        
        for recipient in self.recipients:
            recipient.validate()
        if self.chunked:
                if self.chunk_size is None or self.chunk_size <= 0:
                    raise InvalidHeader("Invalid chunk_size for chunked ciphertext")
    
    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        data: Dict[str, Any] = {
            "version": self.version,
            "aead": self.aead,
            "enc": self.enc,
            "nonce": self.nonce,
            "created_at": self.created_at,
            "chunked": self.chunked,
            "recipients": [recipient.to_dict() for recipient in self.recipients],
        }
        if self.chunk_size is not None:
            data["chunk_size"] = self.chunk_size
        if self.total_size is not None:
            data["total_size"] = self.total_size
        if self.threshold:
            data["threshold"] = self.threshold
        if self.aad_tag:
            data["aad_tag"] = self.aad_tag
        if self.kdf:
            data["kdf"] = self.kdf
        if self.salt:
            data["salt"] = self.salt
        
        return data
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True)

    def aad_bytes(self) -> bytes:
        base: Dict[str, Any] = {
            "version": self.version,
            "aead": self.aead,
            "enc": self.enc,
            "nonce": self.nonce,
            "created_at": self.created_at,
            "chunked": self.chunked,
            "chunk_size": self.chunk_size,
            "threshold": self.threshold,
            "salt": self.salt,
        }
        filtered = {key: value for key, value in base.items() if value is not None}
        return json.dumps(filtered, separators=(",", ":"), sort_keys=True).encode("utf-8")
    
    def nonce_bytes(self) -> bytes:
        return b64d(self.nonce)
    
    @classmethod
    def from_json(cls, raw: str) -> "FileHeader":
        data = json.loads(raw)
        version = str(data.get("version") or data.get("v") or HEADER_VERSION)
        recipients_payload = data.get("recipients", [])
        recipients = [Recipient.from_dict(entry) for entry in recipients_payload]
        chunk_flag = data.get("chunked")
        if chunk_flag is None:
            chunk_flag = bool(data.get("chunk"))
        chunk_size = data.get("chunk_size")
        threshold = data.get("threshold")
        if threshold is None:
            threshold = data.get("threshold_k")
        header = cls(
            version=version,
            aead=(data.get("aead") or data.get("alg") or "AESGCM").upper(),
            enc=(data.get("enc") or "RSA-OAEP").upper(),
            nonce=data.get("nonce") or data.get("content_nonce_b64") or "",
            recipients=recipients,
            created_at=int(data.get("created_at") or int(time.time())),
            chunked=bool(chunk_flag) if chunk_flag is not None else True,
            chunk_size=chunk_size,
            total_size=data.get("total_size"),
            threshold=int(threshold) if threshold else None,
            aad_tag=data.get("aad_tag"),
            kdf=data.get("kdf"),
            salt=data.get("salt"),
        )
        
        if not header.chunked:
            header.chunk_size = None
        header.validate()
        return header

__all__ = ["FileHeader", "Recipient", "HEADER_VERSION"]
    