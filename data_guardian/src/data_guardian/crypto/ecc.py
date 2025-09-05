from __future__ import annotations

"""ECC helpers: X25519 ECDH + HKDF KEK derivation and KEM-style wrapping.

We use ephemeral-static X25519 to derive a KEK via HKDF-SHA256, then wrap
content-encryption keys (CEK) with AEAD (AES-GCM by default, or ChaCha20-Poly1305).
"""

import os
from dataclasses import dataclass
from typing import Tuple, Literal

from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .symmetric import aead_factory


def _hkdf_sha256(secret: bytes, salt: bytes | None, info: bytes, length: int = 32) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(secret)


@dataclass
class X25519EphemeralWrap:
    epk_pem: bytes  # Ephemeral public key (PEM SubjectPublicKeyInfo)
    ct: bytes       # Wrapped CEK (AEAD ciphertext including tag)
    nonce: bytes    # Nonce used in AEAD
    aead: Literal["AESGCM", "CHACHA20"] = "AESGCM"


class X25519KeyPair:
    def __init__(self, private: x25519.X25519PrivateKey | None = None, public=None):
        self._priv = private
        self._pub = public or (private.public_key() if private else None)

    @staticmethod
    def generate() -> "X25519KeyPair":
        priv = x25519.X25519PrivateKey.generate()
        return X25519KeyPair(private=priv)

    # Serialization
    def public_pem(self) -> bytes:
        return self._pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def private_pem_pkcs8(self) -> bytes:
        return self._priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

    # KEM-style wrap using ephemeral-static ECDH
    @staticmethod
    def wrap_cek_for_recipient(
        recipient_pub, cek: bytes, *, aead: Literal["AESGCM", "CHACHA20"] = "AESGCM"
    ) -> X25519EphemeralWrap:
        epk = x25519.X25519PrivateKey.generate()
        shared = epk.exchange(recipient_pub)
        salt = None
        info = b"DG-X25519-CEK"
        kek = _hkdf_sha256(shared, salt, info, length=32)
        nonce = os.urandom(12)
        a = aead_factory(aead, kek)
        ct = a.encrypt(nonce, cek, aad=epk.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ))
        epk_pem = epk.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return X25519EphemeralWrap(epk_pem=epk_pem, ct=ct, nonce=nonce, aead=aead)

    @staticmethod
    def unwrap_cek(
        recipient_priv, wrap: X25519EphemeralWrap
    ) -> bytes:
        epk_pub = serialization.load_pem_public_key(wrap.epk_pem)
        assert isinstance(epk_pub, x25519.X25519PublicKey)
        shared = recipient_priv.exchange(epk_pub)
        kek = _hkdf_sha256(shared, salt=None, info=b"DG-X25519-CEK", length=32)
        a = aead_factory(wrap.aead, kek)
        aad = epk_pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        cek = a.decrypt(wrap.nonce, wrap.ct, aad=aad)
        return cek

