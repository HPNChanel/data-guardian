# Implement detached signing and verification.
from __future__ import annotations
import json
from pathlib import Path
from ..services.key_manager import KeyManager
from ..crypto.signer import Ed25519KeyPair


class SignerService:
    def __init__(self, km: KeyManager | None = None):
        self.km = km or KeyManager()
    
    def sign(self, input_path: Path, sig_path: Path, ed_kid: str) -> None:
        data = input_path.read_bytes()
        priv = self.km.load_ed_private(ed_kid)
        kp = Ed25519KeyPair(private=priv)
        sig_b64 = kp.sign_b64(data)
        sig_path.write_text(sig_b64, encoding="utf-8")
        (sig_path.parent / (sig_path.name + ".json")).write_text(
            json.dumps({"v": 1, "alg": "Ed25519", "kid": ed_kid}, indent=2),
            encoding="utf-8"
        )
    
    def verify(self, input_path: Path, sig_path: Path, meta_path: Path | None = None) -> bool:
        data = input_path.read_bytes()
        sig_b64 = sig_path.read_text(encoding="utf-8").strip()
        meta = (meta_path or (sig_path.parent / (sig_path.name + ".json"))).read_text(encoding="utf-8")
        
        import json
        info = json.loads(meta)
        kid = info["kid"]
        pub = self.km.load_ed_public(kid)
        kp = Ed25519KeyPair(public=pub)
        return kp.verify_b64(data, sig_b64)
