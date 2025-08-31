
from __future__ import annotations
from data_guardian.storage.keystore import KeyStore
from data_guardian.crypto import asymmetric as asy

def export_key(name: str, kind: str, pem: bytes, passphrase: bytes) -> None:
    ks = KeyStore()
    pem = ks.load_private(name, kind, passphrase)
    return pem

def import_key(name: str, kind: str, pem: bytes, passphrase: bytes) -> None:
    ks = KeyStore()
    if kind == "rsa":
        priv = asy.rsa_load_private(pem, passphrase)
        ks.store_private(name, kind, asy.rsa_public_bytes(priv), pem, passphrase)
    elif kind == "ed25519":
        priv = asy.ed25519_load_private(pem, passphrase)
        ks.store_private(name, kind, asy.ed25519_public_bytes(priv), pem, passphrase)
    else:
        raise ValueError("unknown kind")

def rotate_key(name: str, kind: str, passphrase: bytes) -> None:
    #* Naive rotate: just generate a fresh key and overwrite record
    ks = KeyStore()
    if kind == "rsa":
        priv = asy.gen_rsa()
        ks.store_private(name, kind, asy.rsa_public_bytes(priv), asy.rsa_private_bytes(priv, None), passphrase)
    elif kind == "ed25519":
        priv = asy.gen_ed25519()
        ks.store_private(name, kind, asy.ed25519_public_bytes(priv), asy.ed25519_private_bytes(priv, None), passphrase)

def revoke_key(name: str, kind: str) -> None:
    #* Naive revoke: delete record
    ks = KeyStore()
    db = ks._load_db()
    db["keys"] = [k for k in db["keys"] if not (k["name"] == name and k["kind"] == kind)]
    ks._save_db(db)
