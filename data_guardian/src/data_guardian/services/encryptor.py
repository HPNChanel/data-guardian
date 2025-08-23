# Implement hybrid encryption (AES + RSA).
from __future__ import annotations
import json, base64
from pathlib import Path
from ..crypto.symmetric import AesGcm
from ..crypto.asymmetric import RsaKeyPair
from ..services.key_manager import KeyManager
from ..models import Recipient, DgdHeader

def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


class HybridEncryptor:
    """Hybrid: AES-256-GCM content, RSA-OAEP wraps session key"""
    def __init__(self, km: KeyManager | None = None):
        self.km = km or KeyManager()
    
    def encrypt_file(self, input_path: Path, output_path: Path, rsa_kid: str) -> None:
        pt = input_path.read_bytes()
        session_key = AesGcm.gen_key()
        nonce = AesGcm.gen_nonce()
        aes = AesGcm(session_key)
        ct = aes.encrypt(nonce, pt, None)
        
        #* Load recipient public & wrap session key
        pub = self.km.load_rsa_public(rsa_kid)
        wrapped = RsaKeyPair(public=pub).wrap_key(session_key)
        
        header = DgdHeader(
            v=1, alg="AES-256-GCM", enc="RSA-OAEP",
            nonce_b64=_b64e(nonce),
            recipients=[Recipient(kid=rsa_kid, ek_b64=_b64e(wrapped))],
            chunk=False
        )
        header_bytes = (header.to_json() + "\n\n").encode("utf-8")
        output_path.write_bytes(header_bytes + ct)
    