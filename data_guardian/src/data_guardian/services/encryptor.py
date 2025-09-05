# Implement hybrid encryption (AES + RSA).
from __future__ import annotations
import json, base64
from pathlib import Path
from typing import Literal, List
from ..crypto.symmetric import aead_factory, gen_key_for, gen_nonce_for
from ..crypto.asymmetric import RsaKeyPair
from ..crypto.ecc import X25519KeyPair
from ..services.key_manager import KeyManager
from ..models import Recipient, DgdHeader
from ..config import CONFIG

def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


class HybridEncryptor:
    """Hybrid DEM: AEAD content with CEK; KEM/PK wrap CEK (RSA-OAEP or X25519-KEM)."""
    def __init__(self, km: KeyManager | None = None):
        self.km = km or KeyManager()

    def encrypt_file(
        self,
        input_path: Path,
        output_path: Path,
        recipient_kids: list[str],
        *,
        enc: Literal["RSA-OAEP", "X25519-KEM"] = "RSA-OAEP",
        aead: Literal["AESGCM", "CHACHA20"] | None = None,
        oaep_hash: Literal["SHA1", "SHA256", "SHA512"] | None = None,
        threshold_k: int | None = None,
    ) -> None:
        """Encrypt file for one or more recipients.

        - aead: AEAD for content (defaults to CONFIG.crypto.aead)
        - enc: key wrapping scheme (RSA-OAEP or X25519-KEM)
        - oaep_hash: hash for RSA-OAEP (defaults to CONFIG.crypto.rsa_oaep_hash)
        """
        pt = input_path.read_bytes()
        aead_name = (aead or CONFIG.crypto.aead).upper()
        oaep = (oaep_hash or CONFIG.crypto.rsa_oaep_hash).upper()

        cek = gen_key_for(aead_name)
        content_nonce = gen_nonce_for(aead_name)
        a = aead_factory(aead_name, cek)
        ct = a.encrypt(content_nonce, pt, None)

        recipients: List[Recipient] = []
        wrap_material = cek
        shares = None
        if threshold_k and threshold_k > 1:
            from ..crypto.threshold import split_secret
            shares = split_secret(cek, n=len(recipient_kids), k=threshold_k)
        if enc == "RSA-OAEP":
            if shares:
                for (kid, (x, y)) in zip(recipient_kids, shares):
                    pub = self.km.load_rsa_public(kid)
                    share_bytes = int(y).to_bytes(32, "big")
                    wrapped = RsaKeyPair(public=pub).wrap_key(share_bytes, oaep_hash=oaep)  # type: ignore[arg-type]
                    recipients.append(Recipient(kid=kid, ek_b64=_b64e(wrapped), scheme="RSA-OAEP"))
            else:
                for kid in recipient_kids:
                    pub = self.km.load_rsa_public(kid)
                    wrapped = RsaKeyPair(public=pub).wrap_key(cek, oaep_hash=oaep)  # type: ignore[arg-type]
                    recipients.append(Recipient(kid=kid, ek_b64=_b64e(wrapped), scheme="RSA-OAEP"))
        elif enc == "X25519-KEM":
            if shares:
                for (kid, (x, y)) in zip(recipient_kids, shares):
                    pub = self.km.load_x25519_public(kid)
                    share_bytes = int(y).to_bytes(32, "big")
                    w = X25519KeyPair.wrap_cek_for_recipient(pub, share_bytes, aead=aead_name)  # type: ignore[arg-type]
                    recipients.append(
                        Recipient(
                            kid=kid,
                            ek_b64=_b64e(w.ct),
                            scheme="X25519-KEM",
                            epk_pem_b64=_b64e(w.epk_pem),
                            nonce_b64=_b64e(w.nonce),
                        )
                    )
            else:
                for kid in recipient_kids:
                    pub = self.km.load_x25519_public(kid)
                    w = X25519KeyPair.wrap_cek_for_recipient(pub, cek, aead=aead_name)  # type: ignore[arg-type]
                    recipients.append(
                        Recipient(
                            kid=kid,
                            ek_b64=_b64e(w.ct),
                            scheme="X25519-KEM",
                            epk_pem_b64=_b64e(w.epk_pem),
                            nonce_b64=_b64e(w.nonce),
                        )
                    )
        else:
            raise ValueError(f"Unsupported enc scheme: {enc}")

        header = DgdHeader(
            v=1,
            aead=aead_name,
            enc=enc,
            content_nonce_b64=_b64e(content_nonce),
            recipients=recipients,
            chunk=False,
            threshold_k=threshold_k,
        )
        output_path.write_bytes((header.to_json() + "\n\n").encode("utf-8") + ct)
    
