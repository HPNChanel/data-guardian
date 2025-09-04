from __future__ import annotations

import json
import os
import time
import hashlib
from getpass import getpass
from pathlib import Path
from typing import Optional, List

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import serialization

from ..config import CONFIG
from ..storage.paths import PathResolver
from ..models import KeyInfo
from ..utils import b64e, b64d


class KeyStore:
    """Filesystem-backed keystore under `CONFIG.store_dir`.

    Layout:
      - keys.json: index [{kid, alg, label, created_at}]
      - keys/<kid>_pub.pem
      - keys/<kid>_priv.enc  (JSON: {v, alg, salt, nonce, ct})
    """

    def __init__(self, root: Optional[Path | str] = None) -> None:
        self.paths = PathResolver(Path(root) if root else CONFIG.store_dir)
        self.paths.ensure()

    # ----- Index helpers -----
    def _load_index(self) -> dict:
        return json.loads(self.paths.index.read_text(encoding="utf-8"))

    def _save_index(self, data: dict) -> None:
        self.paths.index.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ----- Public API used by KeyManager -----
    def list_keys(self) -> List[KeyInfo]:
        data = self._load_index()
        return [KeyInfo(**k) for k in data.get("keys", [])]

    def make_kid(self, kind: str, public_pem: bytes) -> str:
        prefix = {"rsa": "rsa", "ed": "ed", "ed25519": "ed"}.get(kind, kind)
        h = hashlib.sha256(public_pem).hexdigest()[:10]
        return f"{prefix}_{h}"

    def write_keypair(
        self,
        kid: str,
        public_pem: bytes,
        private_pem_pkcs8: bytes,
        prompt_text: str = "Set passphrase to protect your private key: ",
    ) -> None:
        # Write public key
        (self.paths.keys / f"{kid}_pub.pem").write_bytes(public_pem)

        # Prompt for passphrase (confirm)
        pw1 = getpass(prompt_text)
        pw2 = getpass("Confirm passphrase: ")
        if pw1 != pw2 or not pw1:
            raise ValueError("Passphrases do not match or empty")
        passphrase = pw1.encode("utf-8")

        # Scrypt KDF (configurable)
        kdf_cfg = CONFIG.kdf
        salt = os.urandom(16)
        kdf = Scrypt(salt=salt, length=32, n=kdf_cfg.n, r=kdf_cfg.r, p=kdf_cfg.p)
        key = kdf.derive(passphrase)

        # AES-GCM encrypt
        aes = AESGCM(key)
        nonce = os.urandom(12)
        ct = aes.encrypt(nonce, private_pem_pkcs8, None)

        payload = {
            "v": 1,
            "alg": "AES-256-GCM",
            "salt": b64e(salt),
            "nonce": b64e(nonce),
            "ct": b64e(ct),
        }
        (self.paths.keys / f"{kid}_priv.enc").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def register(self, kid: str, label: str, alg: str) -> None:
        idx = self._load_index()
        keys = idx.get("keys", [])
        created_at = int(time.time())
        # upsert by kid
        keys = [k for k in keys if k.get("kid") != kid]
        keys.append({"kid": kid, "alg": alg, "label": label, "created_at": created_at})
        idx["keys"] = keys
        self._save_index(idx)

    def load_public_key(self, kid: str) -> bytes:
        path = self.paths.keys / f"{kid}_pub.pem"
        if not path.exists():
            raise FileNotFoundError(f"Public key not found: {kid}")
        return path.read_bytes()

    def load_private_key(self, kid: str, purpose_hint: str = ""):
        enc_path = self.paths.keys / f"{kid}_priv.enc"
        if not enc_path.exists():
            raise FileNotFoundError(f"Private key not found: {kid}")
        meta = json.loads(enc_path.read_text(encoding="utf-8"))
        salt = b64d(meta["salt"])  # 16 bytes
        nonce = b64d(meta["nonce"])  # 12 bytes
        ct = b64d(meta["ct"])  # ciphertext+tag

        pw = getpass(f"Enter passphrase to {purpose_hint or 'use private key'} for {kid}: ")
        kdf_cfg = CONFIG.kdf
        kdf = Scrypt(salt=salt, length=32, n=kdf_cfg.n, r=kdf_cfg.r, p=kdf_cfg.p)
        key = kdf.derive(pw.encode("utf-8"))
        aes = AESGCM(key)
        pem = aes.decrypt(nonce, ct, None)
        # Load PEM into key object
        return serialization.load_pem_private_key(pem, password=None)

    def load_private_key_with_passphrase(self, kid: str, passphrase: bytes):
        """Server-friendly variant that does not prompt."""
        enc_path = self.paths.keys / f"{kid}_priv.enc"
        if not enc_path.exists():
            raise FileNotFoundError(f"Private key not found: {kid}")
        meta = json.loads(enc_path.read_text(encoding="utf-8"))
        salt = b64d(meta["salt"])  # 16 bytes
        nonce = b64d(meta["nonce"])  # 12 bytes
        ct = b64d(meta["ct"])  # ciphertext+tag
        kdf_cfg = CONFIG.kdf
        kdf = Scrypt(salt=salt, length=32, n=kdf_cfg.n, r=kdf_cfg.r, p=kdf_cfg.p)
        key = kdf.derive(passphrase)
        aes = AESGCM(key)
        pem = aes.decrypt(nonce, ct, None)
        return serialization.load_pem_private_key(pem, password=None)
