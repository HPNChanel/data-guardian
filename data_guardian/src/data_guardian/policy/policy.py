
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional
from ..storage.keystore import KeyStore

@dataclass
class OperationContext:
    op: str  #* Encrypt, Decrypt, Sign, Verify, SHA256
    actor: str | None  #* Key owner
    details: dict

def check_passphrase_strength(passphrase: str) -> None:
    if len(passphrase) < 8 or not re.search(r"[A-Za-z]", passphrase) or not re.search(r"\d", passphrase):
        raise ValueError("Passphrase too weak: require >= 8 characters, letters and digits")

def enforce(ctx: OperationContext) -> None:
    # Allow-list for known operations
    if ctx.op not in {
        "encrypt", "decrypt", "sign", "verify", "sha256", "list-keys",
        "export-key", "import-key", "doctor", "selftest", "benchmark",
    }:
        raise PermissionError(f"Operation not allowed: {ctx.op}")

    # Enforce key usage policies for operations involving keys
    if ctx.actor:
        ks = KeyStore()
        data = ks._load_index()
        for k in data.get("keys", []):
            if k.get("kid") == ctx.actor:
                expiry = k.get("expiry")
                import time
                if expiry and expiry <= int(time.time()):
                    raise PermissionError(f"Key expired: {ctx.actor}")
                break
