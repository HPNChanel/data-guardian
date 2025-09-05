# Implement hybrid decryption.
from __future__ import annotations
import json, base64
from pathlib import Path
from typing import Literal
from ..crypto.symmetric import aead_factory
from ..crypto.asymmetric import RsaKeyPair
from ..crypto.ecc import X25519EphemeralWrap, X25519KeyPair
from ..services.key_manager import KeyManager
from ..exceptions import InvalidDgdFile
from ..config import CONFIG

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
        body = blob[sep + 2 :]

        enc = header.get("enc", "RSA-OAEP")
        aead_name = header.get("aead", CONFIG.crypto.aead)
        content_nonce = _b64d(header.get("nonce") or header.get("content_nonce_b64"))

        cek = None
        thresh = header.get("threshold_k")
        if not thresh or int(thresh) <= 1:
            if enc == "RSA-OAEP":
                oaep = CONFIG.crypto.rsa_oaep_hash
                for recip in header.get("recipients", []):
                    kid = recip["kid"]
                    try:
                        priv = self.km.load_rsa_private(kid)
                        wrapped = _b64d(recip["ek"]) if "ek" in recip else _b64d(recip["ek_b64"])  # bw compat
                        cek = RsaKeyPair(private=priv).unwrap_key(wrapped, oaep_hash=oaep)  # type: ignore[arg-type]
                        break
                    except Exception:
                        continue
            elif enc == "X25519-KEM":
                for recip in header.get("recipients", []):
                    kid = recip["kid"]
                    try:
                        priv = self.km.load_x25519_private(kid)
                        wrap = X25519EphemeralWrap(
                            epk_pem=_b64d(recip["epk_pem_b64"]),
                            ct=_b64d(recip["ek"]) if "ek" in recip else _b64d(recip["ek_b64"]),
                            nonce=_b64d(recip["nonce"] if "nonce" in recip else recip["nonce_b64"]),
                            aead=aead_name,
                        )
                        cek = X25519KeyPair.unwrap_cek(priv, wrap)
                        break
                    except Exception:
                        continue
            else:
                raise InvalidDgdFile(f"Unsupported enc scheme: {enc}")
        else:
            # threshold flow: unwrap shares and reconstruct CEK
            k = int(thresh)
            shares: list[tuple[int, int]] = []
            recips = header.get("recipients", [])
            if enc == "RSA-OAEP":
                oaep = CONFIG.crypto.rsa_oaep_hash
            for idx, recip in enumerate(recips, start=1):
                kid = recip["kid"]
                try:
                    if enc == "RSA-OAEP":
                        priv = self.km.load_rsa_private(kid)
                        wrapped = _b64d(recip["ek"]) if "ek" in recip else _b64d(recip["ek_b64"])  # bw compat
                        share_bytes = RsaKeyPair(private=priv).unwrap_key(wrapped, oaep_hash=oaep)  # type: ignore[arg-type]
                        y = int.from_bytes(share_bytes, "big")
                        shares.append((idx, y))
                    elif enc == "X25519-KEM":
                        priv = self.km.load_x25519_private(kid)
                        wrap = X25519EphemeralWrap(
                            epk_pem=_b64d(recip["epk_pem_b64"]),
                            ct=_b64d(recip["ek"]) if "ek" in recip else _b64d(recip["ek_b64"]),
                            nonce=_b64d(recip["nonce"] if "nonce" in recip else recip["nonce_b64"]),
                            aead=aead_name,
                        )
                        share_bytes = X25519KeyPair.unwrap_cek(priv, wrap)
                        y = int.from_bytes(share_bytes, "big")
                        shares.append((idx, y))
                except Exception:
                    continue
                if len(shares) >= k:
                    break
            if len(shares) < k:
                raise InvalidDgdFile("Not enough shares to reconstruct CEK")
            from ..crypto.threshold import combine_shares
            cek = combine_shares(shares, k)

        if cek is None:
            raise InvalidDgdFile("No matching recipient key could unwrap CEK")
        a = aead_factory(aead_name, cek)
        pt = a.decrypt(content_nonce, body, None)
        output_path.write_bytes(pt)
