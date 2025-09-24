
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
