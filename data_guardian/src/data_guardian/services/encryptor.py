# Implement hybrid encryption (AES + RSA).
from __future__ import annotations
import hashlib
import struct
import time
from pathlib import Path
from typing import Literal, List, Sequence

from ..config import CONFIG
from ..crypto.asymmetric import RsaKeyPair
from ..crypto.ecc import X25519KeyPair
from ..crypto.symmetric import (
    aead_factory,
    derive_chunk_nonce, 
    gen_key_for, 
    gen_nonce_for
)
from ..crypto.threshold import split_secret
from ..services.key_manager import KeyManager
from ..storage.file_io import open_encrypted_writer, write_chunk
from ..storage.header import FileHeader, Recipient
from ..utils import b64e
from ..utils.errors import InvalidHeader


class HybridEncryptor:
    """Hybrid DEM: AEAD content with CEK; KEM/PK wrap CEK (RSA-OAEP or X25519-KEM)."""
    def __init__(self, km: KeyManager | None = None):
        manager = km or KeyManager()
        self.km = manager  #* Keep public one
        self._km = manager

    def encrypt_file(
        self,
        input_path: Path,
        output_path: Path,
        recipient_kids: Sequence[str],
        *,
        enc: Literal["RSA-OAEP", "X25519-KEM"] = "RSA-OAEP",
        aead: Literal["AESGCM", "CHACHA20"] | None = None,
        oaep_hash: Literal["SHA1", "SHA256", "SHA512"] | None = None,
        threshold_k: int | None = None,
        aad: bytes | None = None,
        chunk_size: int | None = None,
    ) -> FileHeader:
        """Encrypt file for one or more recipients.

        - aead: AEAD for content (defaults to CONFIG.crypto.aead)
        - enc: key wrapping scheme (RSA-OAEP or X25519-KEM)
        - oaep_hash: hash for RSA-OAEP (defaults to CONFIG.crypto.rsa_oaep_hash)
        """
        if not recipient_kids:
            raise InvalidHeader("At least one recipient is required")
        aead_name = (aead or CONFIG.crypto.aead).upper()
        enc_scheme = enc.upper()
        oaep_alg = (oaep_hash or CONFIG.crypto.rsa_oaep_hash).upper()
        chunk = chunk_size or CONFIG.crypto.default_chunk_size
        
        cek = gen_key_for(aead_name)
        base_nonce = gen_nonce_for(aead_name)
        
        recipients: List[Recipient] = []
        shares = None
        if threshold_k and threshold_k > 1:
            shares = split_secret(cek, n=len(recipient_kids), k=threshold_k)
            
        for idx, kid in enumerate(recipient_kids):
            share_index = None
            material = cek
            if shares:
                share_index, share_value = shares[idx]
                material = int(share_value).to_bytes(len(cek), "big")
            
            if enc_scheme == "RSA-OAEP":
                pub = self._km.load_rsa_public(kid)
                wrapped = RsaKeyPair(public=pub).wrap_key(material, oaep_hash=oaep_alg)
                recipients.append(
                    Recipient(
                        kid=kid,
                        scheme="RSA-OAEP",
                        enc_key=b64e(wrapped),
                        share_index=share_index,
                    )
                )
            elif enc_scheme == "X25519-KEM":
                pub = self._km.load_x25519_public(kid)
                wrap = X25519KeyPair(public=pub).wrap_cek_for_recipient(pub, material, aead=aead_name)
                recipients.append(
                    Recipient(
                        kid=kid,
                        scheme="X25519-KEM",
                        enc_key=b64e(wrap.ct),
                        ephemeral_public=b64e(wrap.epk_pem),
                        nonce=b64e(wrap.nonce),
                        share_index=share_index,
                    )
                )
            else:
                raise InvalidHeader(f"Unsupported key wrap scheme: {enc_scheme}")
        
        header = FileHeader(
            aead=aead_name,
            enc=enc_scheme, 
            nonce=b64e(base_nonce),
            recipients=recipients,
            chunked=True,
            chunk_size=chunk,
            total_size=input_path.stat().st_size,
            threshold=threshold_k,
        )
        if aad:
            header.aad_tag = b64e(hashlib.sha256(aad).digest())
        
        aead_impl = aead_factory(aead_name, cek)
        aad_material = header.aad_bytes()
        if aad:
            aad_material += aad
        
        wrote = False
        with input_path.open("rb") as source, open_encrypted_writer(output_path, header) as sink:
            for index, chunk_data in enumerate(iter(lambda: source.read(chunk), b"")):
                nonce = derive_chunk_nonce(base_nonce, index)
                assoc = aad_material + struct.pack(">I", index)
                ciphertext = aead_impl.encrypt(nonce, chunk_data, assoc)
                write_chunk(sink, index, ciphertext)
                wrote = True
            if not wrote:
                nonce = derive_chunk_nonce(base_nonce, 0)
                assoc = aad_material + struct.pack(">I", 0)
                ciphertext = aead_impl.encrypt(nonce, b"", assoc)
                write_chunk(sink, 0, ciphertext)
        return header
