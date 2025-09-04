import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AES_KEY_SIZE = 32  # 256-bit
NONCE_SIZE = 12


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
