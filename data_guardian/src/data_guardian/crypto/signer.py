# Implement Ed25519 signer and verifier (OOP).
from __future__ import annotations
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

class Ed25519KeyPair:
    def __init__(self, private=None, public=None):
        self._priv = private
        self._pub = public or (private.public_key() if private else None)
    
    @staticmethod
    def generate() -> "Ed25519KeyPair":
        priv = ed25519.Ed25519PrivateKey.generate()
        return Ed25519KeyPair(private=priv)
    
    def public_pem(self) -> bytes:
        return self._pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    
    def private_pem_pkcs8(self) -> bytes:
        return self._priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    def sign_b64(self, data: bytes) -> str:
        sig = self._priv.sign(data)
        return base64.b64encode(sig).decode()
    
    def verify_b64(self, data: bytes, sig_b64: str) -> bool:
        sig = base64.b64decode(sig_b64.encode())
        try:
            self._pub.verify(sig, data)
            return True
        except Exception:
            return False
