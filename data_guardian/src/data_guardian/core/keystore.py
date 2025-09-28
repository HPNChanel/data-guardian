
from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Iterable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from data_guardian.core.exceptions import CryptoError


class FileKeyStore:
    """Filesystem-backed keystore with strict permission enforcement"""
    
    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path
        
    def load_private_key(self, *, key_id: str, passphrase: bytes | None = None) -> rsa.RSAPrivateKey:
        key_path = self._resolve_key_path(key_id)
        self._assert_permissions(key_path)
        pem = key_path.read_bytes()
        key = serialization.load_pem_private_key(pem, password=passphrase)
        if not isinstance(key, rsa.RSAPrivateKey):
            raise CryptoError("Expected RSA private key")
        return key
    
    def store_private_key(
        self,
        *,
        key_id: str,
        private_key: rsa.RSAPrivateKey,
        passphrase: bytes | None = None,
    ) -> Path:
        key_path = self._resolve_key_path(key_id)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(passphrase) if passphrase else serialization.NoEncryption(),
        )
        with open(key_path, "wb") as handle:
            handle.write(pem)
        os.chmod(key_path, 0o600)
        return key_path
    
    def list_private_keys(self) -> Iterable[str]:
        if not self._base_path.exists():
            return []
        return [
            path.stem for path in self._base_path.glob("*.pem") if path.is_file()
        ]
    
    def _resolve_key_path(self, key_id: str) -> Path:
        safe_key_id = key_id.replace("/", "_")
        # TODO: enforce stricter key ID policy once organizational scheme decided
        return self._base_path / f"{safe_key_id}.pem"

    def _assert_permissions(self, key_path: Path) -> None:
        if not key_path.exists():
            raise CryptoError(f"Key file {key_path} does not exist")
        mode = stat.S_IMODE(key_path.stat().st_mode)
        if mode != 0o600:
            raise CryptoError(f"Insecure permissions on {key_path}: expected 0o600, found{oct(mode)}")
