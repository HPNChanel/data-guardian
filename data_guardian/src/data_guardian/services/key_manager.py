# Manage the lifecycle of keys (generate, list, load).
from __future__ import annotations
from typing import List
from cryptography.hazmat.primitives import serialization
from ..storage.keystore import KeyStore
from ..models import KeyInfo
from ..crypto.asymmetric import RsaKeyPair
from ..crypto.signer import Ed25519KeyPair

class KeyManager:
    """Create & list keys via KeyStore"""
    def __init__(self, store: KeyStore | None = None):
        self.store = store or KeyStore()
    
    def list_keys(self) -> List[KeyInfo]:
        return self.store.list_keys()
    
    def create_rsa(self, label:str) -> str:
        kp = RsaKeyPair.generate()
        kid = self.store.make_kid("rsa", kp.public_pem())
        self.store.write_keypair(kid, kp.public_pem(), kp.private_pem_pkcs8(),
                                "Set passphrase to protect your RSA private key: ")
        self.store.register(kid, label, "RSA")
        return kid
    
    def create_ed25519(self, label: str) -> str:
        kp = Ed25519KeyPair.generate()
        kid = self.store.make_kid("ed", kp.public_pem())
        self.store.write_keypair(kid, kp.public_pem(), kp.private_pem_pkcs8(),
                                "Set passphrase to protect your Ed25519 private key: ")
        self.store.register(kid, label, "ED25519")
        return kid
    
    #* Loaders
    def load_rsa_public(self, kid: str):
        return self.store.load_public_key(kid)
    
    def load_rsa_private(self, kid: str):
        return self.store.load_private_key(kid, "decrypt unwrap session-key")
    
    def load_ed_public(self, kid: str):
        return self.store.load_public_key(kid)
    
    def load_ed_private(self, kid: str):
        return self.store.load_private_key(kid, "sign file")
    