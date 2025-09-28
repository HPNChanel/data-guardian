
from __future__ import annotations

from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey
)

from data_guardian.core.exceptions import CryptoError


@dataclass(slots=True)
class Signature:
    signer_id: str
    signature: bytes
    
    
class Ed25519Signer:
    """Thin wrapper around Ed25519 that normalizes error handling"""
    
    def __init__(self, *, private_key: Ed25519PrivateKey | None = None, public_key: Ed25519PublicKey | None = None) -> None:
        if not private_key and not public_key:
            raise CryptoError("At least one of private_key or public_key is required")
        self._private_key = private_key
        self._public_key = public_key or private_key.public_key()  #* type: ignore[union-attr]
    
    @classmethod
    def from_private_bytes(cls, data: bytes) -> Ed25519Signer:
        return cls(private_key=Ed25519PrivateKey.from_private_bytes(data))
    
    @classmethod
    def from_public_bytes(cls, data: bytes) -> Ed25519Signer:
        return cls(public_key=Ed25519PublicKey.from_public_bytes(data))
    
    def sign(self, *, message: bytes) -> bytes:
        if not self._private_key:
            raise CryptoError("Signing requested without private key material")
        return self._private_key.sign(message)
    
    def verify(self, *, message: bytes, signature: bytes) -> None:
        try:
            self._public_key.verify(signature, message)
        except InvalidSignature as exc:
            raise CryptoError("Signature verification failed") from exc
