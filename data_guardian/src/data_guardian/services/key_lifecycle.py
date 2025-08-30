
from __future__ import annotations
from data_guardian.storage.keystore import KeyStore
from data_guardian.crypto import asymmetric as asy

def export_key(name: str, kind: str, pem: bytes, passphrase: bytes) -> None:
    ks = KeyStore()
    pem = ks.load_private(name, kind, passphrase)
    return pem
