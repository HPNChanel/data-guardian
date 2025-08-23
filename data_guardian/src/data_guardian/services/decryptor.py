# Implement hybrid decryption.
from __future__ import annotations
import json, base64
from pathlib import Path
from ..crypto.symmetric import AesGcm
from ..crypto.asymmetric import RsaKeyPair
from ..services.key_manager import KeyManager
from ..exceptions import InvalidDgdFile

def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


class HybridDecryptor:
    def __init__(self, km: KeyManager | None = None):
        self.km = km or KeyManager()
    
    def decrypt_file(self, input_path: Path, output_path: Path) -> None:
        blob = input_path.read_bytes()
        sep = blob.find(b"\n\n")
        if sep < 0:
            raise InvalidDgdFile("Missing header separator")
        header = json.loads(blob[:sep].decode("utf-8"))
        body = blob[sep+2:]
        
        recip = header["recipients"][0]  #* Single recipient for MVP
        rsa_kid = recip["kid"]
        ek = _b64d(recip["ek"])
        nonce = _b64d(header["nonce"])
        
        priv = self.km.load_rsa_private(rsa_kid)
        session_key = RsaKeyPair(private=priv).unwrap_key(ek)
        aes = AesGcm(session_key)
        pt = aes.decrypt(nonce, body, None)
        output_path.write_bytes(pt)
