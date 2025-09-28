
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from data_guardian.core.exceptions import CryptoError

AES256_KEY_SIZE: Final[int] = 32
NONCE_PREFIX_SIZE: Final[int] = 4
COUNTER_SIZE: Final[int] = 8
IV_SIZE_BYTES: Final[int] = NONCE_PREFIX_SIZE + COUNTER_SIZE
MAX_CHUNKS: Final[int] = 2 ** (COUNTER_SIZE * 8)


@dataclass(slots=True)
class AEADEncryptionResult:
    ciphertext: bytes
    nonce: bytes


class AESGCMCipher:
    """AES-256-GCM with per-chunk unique nonces derived via HKDF(prefix) +counter"""
    def __init__(self, *, key: bytes, salt: bytes, aad_domain: bytes) -> None:
        if len(key) != AES256_KEY_SIZE:
            raise CryptoError("AES-256-GCM requires a 32-byte key")
        if len(salt) < 16:
            raise CryptoError("HKDF salt must be at least 128 bits")
        self._key = key
        self._aad_domain = aad_domain
        self._nonce_prefix = HKDF(
            algorithm=hashes.SHA256(),
            length=NONCE_PREFIX_SIZE,
            salt=salt,
            info=b"DGAR-nonce-prefix" + aad_domain,
        ).derive(key)
        self._aead = AESGCM(key)
    
    def encrypt(self, *, plaintext: bytes, chunk_index: int, aad: bytes) -> AEADEncryptionResult:
        nonce = self._derive_nonce(chunk_index)
        full_aad = self._aad_domain + aad
        ciphertext = self._aead.encrypt(nonce, plaintext, full_aad)
        return AEADEncryptionResult(ciphertext=ciphertext, nonce=nonce)
    
    def decrypt(self, *, ciphertext: bytes, chunk_index: int, aad: bytes) -> bytes:
        nonce = self._derive_nonce(chunk_index)
        full_aad = self._aad_domain + aad
        try:
            return self._aead.decrypt(nonce, ciphertext, full_aad)
        except InvalidTag as exc:
            raise CryptoError("AEAD tag verification failed") from exc
    
    def _derive_nonce(self, chunk_index: int) -> bytes:
        if not 0 <= chunk_index < MAX_CHUNKS:
            raise CryptoError("AES-GCM chunk counter exhausted")
        counter_bytes = chunk_index.to_bytes(COUNTER_SIZE, byteorder="big")
        return self._nonce_prefix + counter_bytes
