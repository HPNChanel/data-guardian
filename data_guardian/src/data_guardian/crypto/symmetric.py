import os
from typing import Literal
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305

AES_KEY_SIZE = 32  #* 256-bit
NONCE_SIZE = 12
MAX_CHUNKS = 2**32

# Functional helpers (legacy)
def gen_key() -> bytes:
    return os.urandom(AES_KEY_SIZE)


def encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    ct = aesgcm.encrypt(nonce, plaintext, aad)
    return nonce, ct


def decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes:
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, aad)


# OO helper used by services
class AesGcm:
    @staticmethod
    def gen_key() -> bytes:
        return os.urandom(AES_KEY_SIZE)

    @staticmethod
    def gen_nonce() -> bytes:
        return os.urandom(NONCE_SIZE)

    def __init__(self, key: bytes):
        self._key = key
        self._aes = AESGCM(key)

    def encrypt(self, nonce: bytes, pt: bytes, aad: bytes | None = None) -> bytes:
        return self._aes.encrypt(nonce, pt, aad)

    def decrypt(self, nonce: bytes, ct: bytes, aad: bytes | None = None) -> bytes:
        return self._aes.decrypt(nonce, ct, aad)


class ChaCha20:
    """ChaCha20-Poly1305 AEAD wrapper with API parity to AesGcm"""

    KEY_SIZE = 32
    NONCE_SIZE = 12

    @staticmethod
    def gen_key() -> bytes:
        return os.urandom(ChaCha20.KEY_SIZE)

    @staticmethod
    def gen_nonce() -> bytes:
        return os.urandom(ChaCha20.NONCE_SIZE)

    def __init__(self, key: bytes):
        self._key = key
        self._aead = ChaCha20Poly1305(key)

    def encrypt(self, nonce: bytes, pt: bytes, aad: bytes | None = None) -> bytes:
        return self._aead.encrypt(nonce, pt, aad)

    def decrypt(self, nonce: bytes, ct: bytes, aad: bytes | None = None) -> bytes:
        return self._aead.decrypt(nonce, ct, aad)


def aead_factory(name: Literal["AESGCM", "CHACHA20"], key: bytes):
    name_up = name.upper()
    if name_up == "AESGCM":
        return AesGcm(key)
    if name_up == "CHACHA20":
        return ChaCha20(key)
    raise ValueError(f"Unsupported AEAD: {name}")

def gen_key_for(name: Literal["AESGCM", "CHACHA20"]) -> bytes:
    name_up = name.upper()
    if name_up == "AESGCM":
        return AesGcm.gen_key()
    if name_up == "CHACHA20":
        return ChaCha20.gen_key()
    raise ValueError(f"Unsupported AEAD: {name}")

def gen_nonce_for(name: Literal["AESGCM", "CHACHA20"]) -> bytes:
    name_up = name.upper()
    if name_up == "AESGCM":
        return AesGcm.gen_nonce()
    if name_up == "CHACHA20":
        return ChaCha20.gen_nonce()
    raise ValueError(f"Unsupported AEAD: {name}")


def derive_chunk_nonce(base_nonce: bytes, chunk_index: int) -> bytes:
    """Derive a deterministic nonce for the given chunk index"""
    if len(base_nonce) != NONCE_SIZE:
        raise ValueError("Expected a 96-bit base nonce")
    if not 0 <= chunk_index < MAX_CHUNKS:
        raise ValueError("Chunk index out of range")
    
    prefix = base_nonce[:-4]
    counter = int.from_bytes(base_nonce[-4:], "big")
    new_counter = (counter + chunk_index) % MAX_CHUNKS
    return prefix + new_counter.to_bytes(4, "big")
