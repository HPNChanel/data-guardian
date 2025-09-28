# Implement hybrid decryption.
from __future__ import annotations
import hashlib
from typing import Optional
from pathlib import Path
import struct

from ..config import CONFIG
from ..crypto.asymmetric import RsaKeyPair
from ..crypto.ecc import X25519EphemeralWrap, X25519KeyPair
from ..crypto.symmetric import aead_factory, derive_chunk_nonce
from ..crypto.threshold import combine_shares
from ..services.key_manager import KeyManager
from ..storage.file_io import iter_chunks, open_encrypted_reader
from ..storage.header import FileHeader, Recipient
from ..utils import b64d, b64e
from ..utils.errors import InvalidCiphertext, constant_time_compare


class HybridDecryptor:
    def __init__(self, km: KeyManager | None = None):
        self._km = km or KeyManager()
    
    def decrypt_file(self, input_path: Path, output_path: Path, aad: bytes | None = None) -> None:
        with open_encrypted_reader(input_path) as (header, handle):
            cek = self._unwrap_cek(header)
            base_nonce = header.nonce_bytes()
            aead_impl = aead_factory(header.aead, cek)
            
            aad_material = header.aad_bytes()
            if header.aad_tag:
                if not aad:
                    raise InvalidCiphertext("AAD required to decrypt this payload")
                provided = b64e(hashlib.sha256(aad).digest())
                if not constant_time_compare(provided, header.aad_tag):
                    raise InvalidCiphertext("AAD mismatch")
                aad_material += aad
            elif aad:
                raise InvalidCiphertext("AAD provided but ciphertext not sealed with AAD")
            
            with output_path.open("wb") as dest:
                if header.chunked:
                    for index, payload in iter_chunks(handle):
                        nonce = derive_chunk_nonce(base_nonce, index)
                        assoc = aad_material + struct.pack(">I", index)
                        plaintext = aead_impl.decrypt(nonce, payload, assoc)
                        dest.write(plaintext)
                else:
                    payload = handle.read()
                    assoc = aad_material + struct.pack(">I", 0)
                    plaintext = aead_impl.decrypt(base_nonce, payload, assoc)
                    dest.write(plaintext)
    
    def _unwrap_cek(self, header: FileHeader) -> bytes:
        enc_scheme = header.enc
        if header.threshold and header.threshold > 1:
            shares = []
            for recipient in header.recipients:
                material = self._unwrap_for_recipient(recipient, enc_scheme, header.aead)
                if material is None:
                    continue
                index = recipient.share_index or (len(shares) + 1)
                shares.append((index, int.from_bytes(material, "big")))
                if len(shares) >= header.threshold:
                    break
            if len(shares) < header.threshold:
                raise InvalidCiphertext("Insufficient shares to reconstruct CEX")
            return combine_shares(shares=header.threshold)

        for recipient in header.recipients:
            material = self._unwrap_for_recipient(recipient, enc_scheme, header.aead)
            if material is not None:
                return material
        raise InvalidCiphertext("No matching key to unwrap CEX")
    
    def _unwrap_for_recipient(
        self,
        recipient: Recipient,
        scheme: str,
        aead_name: str,
    ) -> Optional[bytes]:
        try:
            if scheme == "RSA-OAEP":
                priv = self._km.load_rsa_private(recipient.kid)
                wrapped = b64d(recipient.enc_key)
                return RsaKeyPair(private=priv).unwrap_key(wrapped, oaep_hash=CONFIG.crypto.rsa_oaep_hash)
            if scheme == "X25519-KEM":
                if not recipient.ephemeral_public or not recipient.nonce:
                    return None
                priv = self._km.load_x25519_private(recipient.kid)
                wrap = X25519EphemeralWrap(
                    epk_pem=b64d(recipient.ephemeral_public),
                    ct=b64d(recipient.enc_key),
                    nonce=b64d(recipient.nonce),
                    aead=aead_name,
                )
                return X25519KeyPair.unwrap_cek(priv, wrap)
        except Exception:
            return None

        return None
