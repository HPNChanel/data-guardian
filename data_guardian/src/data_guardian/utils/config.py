
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

_STORE_ENV = "DG_STORE_DIR"


def _default_store() -> Path:
    value = os.getenv(_STORE_ENV)
    if value:
        return Path(value).expanduser()
    
    return Path.home() / ".data_guardian"


@dataclass(frozen=True)
class KdfConfig:
    """Parameters for deriving keys with scrypt"""
    
    algorithm: str = "scrypt"
    length: int = 32
    salt_length: int = 16
    n: int = 2**15
    r: int = 8
    p: int = 1
    
    def as_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "length": self.length,
            "salt_length": self.salt_length,
            "n": self.n,
            "r": self.r,
            "p": self.p,
        }


@dataclass(frozen=True)
class CryptoDefaults:
    aead: str = "AESGCM"
    rsa_oaep_hash: str = "SHA256"
    default_chunk_size: int = 1024 * 1024


@dataclass(frozen=True)
class AuditConfig:
    json_stdout: bool = True
    syslog_host: str | None = None
    syslog_port: int = 514


@dataclass(frozen=True)
class AppConfig:
    store_dir: Path = field(default_factory=_default_store)
    kdf: KdfConfig = field(default_factory=KdfConfig)
    crypto: CryptoDefaults = field(default_factory=CryptoDefaults)
    audit: AuditConfig = field(default_factory=AuditConfig)


CONFIG = AppConfig()

__all__ = ["AppConfig", "AuditConfig", "CONFIG", "CryptoDefaults", "KdfConfig"]
