
from __future__ import annotations
import re
from dataclasses import dataclass

@dataclass
class OperationContext:
    op: str  #* Encrypt, Decrypt, Sign, Verify, SHA256
    actor: str | None  #* Key owner
    details: dict

def check_passphrase_strength(passphrase: str) -> None:
    if len(passphrase) < 8 or not re.search(r"[A-Za-z]", passphrase) or not re.search(r"\d", passphrase):
        raise ValueError("Passphrase too weak: require >= 8 characters, letters and digits")

def enforce(ctx: OperationContext) -> None:
    #* Example allowist: no restrictions here, but hook for future
    if ctx.op not in {"encrypt", "decrypt", "sign", "verify", "sha256", "list-keys", "export-key", "import-key"}:
        raise PermissionError(f"Operation not allowed: {ctx.op}")
