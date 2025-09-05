"""Asymmetric primitives and small OOP wrappers used by services.

This module exposes both functional helpers (legacy) and thin classes used by
HybridEncryptor/HybridDecryptor via KeyManager.
"""

from typing import Literal
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ed25519
from cryptography.hazmat.primitives import serialization, hashes


# ---------- RSA helpers (functional) ----------
def gen_rsa() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=3072)


def rsa_public_bytes(priv: rsa.RSAPrivateKey) -> bytes:
    return priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def rsa_private_bytes(priv: rsa.RSAPrivateKey, passphrase: bytes | None = None) -> bytes:
    if passphrase:
        encryption = serialization.BestAvailableEncryption(passphrase)
    else:
        encryption = serialization.NoEncryption()

    return priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        encryption,
    )


def rsa_load_private(pem: bytes, passphrase: bytes | None = None) -> rsa.RSAPrivateKey:
    return serialization.load_pem_private_key(pem, password=passphrase)


def _hash_alg(name: Literal["SHA1", "SHA256", "SHA512"]):
    n = name.upper()
    if n == "SHA1":
        return hashes.SHA1()
    if n == "SHA256":
        return hashes.SHA256()
    if n == "SHA512":
        return hashes.SHA512()
    raise ValueError(f"Unsupported OAEP hash: {name}")


def rsa_encrypt(pub, data: bytes, oaep_hash: Literal["SHA1", "SHA256", "SHA512"] = "SHA256") -> bytes:
    h = _hash_alg(oaep_hash)
    return pub.encrypt(
        data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=h),
            algorithm=h,
            label=None,
        ),
    )


def rsa_decrypt(priv, ct: bytes, oaep_hash: Literal["SHA1", "SHA256", "SHA512"] = "SHA256") -> bytes:
    h = _hash_alg(oaep_hash)
    return priv.decrypt(
        ct,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=h),
            algorithm=h,
            label=None,
        ),
    )


# ---------- Ed25519 helpers (functional) ----------
def gen_ed25519() -> ed25519.Ed25519PrivateKey:
    return ed25519.Ed25519PrivateKey.generate()


def ed25519_public_bytes(priv: ed25519.Ed25519PrivateKey) -> bytes:
    return priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def ed25519_private_bytes(
    priv: ed25519.Ed25519PrivateKey, passphrase: bytes | None = None
) -> bytes:
    if passphrase:
        encryption = serialization.BestAvailableEncryption(passphrase)
    else:
        encryption = serialization.NoEncryption()

    return priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        encryption,
    )


def ed25519_load_private(
    pem: bytes, passphrase: bytes | None = None
) -> ed25519.Ed25519PrivateKey:
    return serialization.load_pem_private_key(pem, password=passphrase)


def sign(priv: ed25519.Ed25519PrivateKey, data: bytes) -> bytes:
    return priv.sign(data)


def verify(pub, sig: bytes, data: bytes) -> None:
    pub.verify(sig, data)


# ---------- OOP wrappers used by services ----------
class RsaKeyPair:
    """Minimal OO wrapper providing wrap/unwrap and serialization helpers."""

    def __init__(self, private: rsa.RSAPrivateKey | None = None, public=None):
        self._priv = private
        self._pub = public or (private.public_key() if private else None)

    @staticmethod
    def generate(bits: int = 3072) -> "RsaKeyPair":
        priv = rsa.generate_private_key(public_exponent=65537, key_size=bits)
        return RsaKeyPair(private=priv)

    # Serialization helpers
    def public_pem(self) -> bytes:
        return self._pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def private_pem_pkcs8(self, passphrase: bytes | None = None) -> bytes:
        if passphrase:
            alg = serialization.BestAvailableEncryption(passphrase)
        else:
            alg = serialization.NoEncryption()
        return self._priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=alg,
        )

    # RSA-OAEP key wrap/unwrap
    def wrap_key(self, data: bytes, oaep_hash: Literal["SHA1", "SHA256", "SHA512"] = "SHA256") -> bytes:
        h = _hash_alg(oaep_hash)
        return self._pub.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=h),
                algorithm=h,
                label=None,
            ),
        )

    def unwrap_key(self, ct: bytes, oaep_hash: Literal["SHA1", "SHA256", "SHA512"] = "SHA256") -> bytes:
        h = _hash_alg(oaep_hash)
        return self._priv.decrypt(
            ct,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=h),
                algorithm=h,
                label=None,
            ),
        )
