from __future__ import annotations

import os
import json
import struct
from pathlib import Path
from typing import Literal, List, Optional

from tqdm import tqdm

from ..crypto.symmetric import aead_factory, gen_key_for, gen_nonce_for
from ..crypto.asymmetric import RsaKeyPair
from ..crypto.ecc import X25519EphemeralWrap, X25519KeyPair
from ..services.key_manager import KeyManager
from ..models import Recipient, DgdHeader
from ..utils import b64e, b64d
from ..config import CONFIG


class StreamEncryptor:
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
        chunk_size: int = 1024 * 1024,
        resume: bool = True,
    ) -> None:
        aead_name = (aead or CONFIG.crypto.aead).upper()
        oaep = (oaep_hash or CONFIG.crypto.rsa_oaep_hash).upper()

        cek = gen_key_for(aead_name)
        content_nonce = gen_nonce_for(aead_name)

        # recipients wrap CEK (non-threshold for streaming to keep simple here)
        recipients: List[Recipient] = []
        if enc == "RSA-OAEP":
            for kid in recipient_kids:
                pub = self.km.load_rsa_public(kid)
                wrapped = RsaKeyPair(public=pub).wrap_key(cek, oaep_hash=oaep)  # type: ignore[arg-type]
                recipients.append(Recipient(kid=kid, ek_b64=b64e(wrapped), scheme="RSA-OAEP"))
        else:
            for kid in recipient_kids:
                pub = self.km.load_x25519_public(kid)
                w = X25519KeyPair.wrap_cek_for_recipient(pub, cek, aead=aead_name)  # type: ignore[arg-type]
                recipients.append(Recipient(kid=kid, ek_b64=b64e(w.ct), scheme="X25519-KEM", epk_pem_b64=b64e(w.epk_pem), nonce_b64=b64e(w.nonce)))

        total_size = input_path.stat().st_size
        header = DgdHeader(
            v=1,
            aead=aead_name,
            enc=enc,
            content_nonce_b64=b64e(content_nonce),
            recipients=recipients,
            chunk=True,
            threshold_k=None,
            chunk_size=chunk_size,
            total_size=total_size,
        )

        with open(input_path, "rb") as fi, open(output_path, "ab" if resume and output_path.exists() else "wb") as fo:
            if fo.tell() == 0:
                fo.write((header.to_json() + "\n\n").encode("utf-8"))

            a = aead_factory(aead_name, cek)
            # Determine starting chunk for resume
            start_chunk = 0
            if fo.tell() > 0:
                # naive: require external tracking; here we just append from start
                pass
            pos = start_chunk * chunk_size
            if pos:
                fi.seek(pos)

            pbar = tqdm(total=total_size, unit="B", unit_scale=True, initial=pos, desc="Encrypting")
            idx = start_chunk
            while True:
                chunk = fi.read(chunk_size)
                if not chunk:
                    break
                # derive per-chunk nonce from base nonce + idx (XOR into last 4 bytes)
                base = bytearray(content_nonce)
                for i in range(4):
                    base[-1 - i] ^= (idx >> (8 * i)) & 0xFF
                nonce = bytes(base)
                ct = a.encrypt(nonce, chunk, aad=str(idx).encode())
                # write: 4-byte length + 4-byte index + ciphertext
                fo.write(struct.pack(">II", len(ct), idx))
                fo.write(ct)
                idx += 1
                pbar.update(len(chunk))
            pbar.close()


class StreamDecryptor:
    def __init__(self, km: KeyManager | None = None):
        self.km = km or KeyManager()

    def decrypt_file(self, input_path: Path, output_path: Path) -> None:
        with open(input_path, "rb") as fi:
            blob = fi.read()
        sep = blob.find(b"\n\n")
        if sep < 0:
            raise ValueError("Malformed header")
        header = json.loads(blob[:sep].decode("utf-8"))
        body = blob[sep + 2 :]
        aead = header.get("aead", CONFIG.crypto.aead)
        enc = header.get("enc", "RSA-OAEP")
        content_nonce = b64d(header.get("nonce") or header.get("content_nonce_b64"))

        cek = None
        if enc == "RSA-OAEP":
            for r in header.get("recipients", []):
                try:
                    priv = self.km.load_rsa_private(r["kid"])  # prompt per key
                    wrapped = b64d(r.get("ek") or r.get("ek_b64"))
                    cek = RsaKeyPair(private=priv).unwrap_key(wrapped)
                    break
                except Exception:
                    continue
        else:
            for r in header.get("recipients", []):
                try:
                    priv = self.km.load_x25519_private(r["kid"])  # prompt per key
                    wrap = X25519EphemeralWrap(
                        epk_pem=b64d(r["epk_pem_b64"]),
                        ct=b64d(r.get("ek") or r.get("ek_b64")),
                        nonce=b64d(r.get("nonce") or r.get("nonce_b64")),
                        aead=aead,
                    )
                    cek = X25519KeyPair.unwrap_cek(priv, wrap)
                    break
                except Exception:
                    continue
        if cek is None:
            raise ValueError("No matching key to unwrap CEK")

        a = aead_factory(aead, cek)
        # parse chunks
        import io as _io
        bio = _io.BytesIO(body)
        idx = 0
        with open(output_path, "wb") as fo:
            while True:
                hdr = bio.read(8)
                if not hdr:
                    break
                (length, chunk_idx) = struct.unpack(">II", hdr)
                ct = bio.read(length)
                base = bytearray(content_nonce)
                for i in range(4):
                    base[-1 - i] ^= (chunk_idx >> (8 * i)) & 0xFF
                nonce = bytes(base)
                pt = a.decrypt(nonce, ct, aad=str(chunk_idx).encode())
                fo.write(pt)
                idx += 1

