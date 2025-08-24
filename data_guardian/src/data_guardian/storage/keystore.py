# Implement the KeyStore class for reading/writing keys and managing the JSON index.
from __future__ import annotations
import json, time, hashlib, base64
from pathlib import Path
from typing import List
from getpass import getpass
from cryptography.hazmat.primitives import serialization
from ..models import KeyInfo
from ..exceptions import KeyNotFound, InvalidPassphrase
from .paths import PathResolver
from ..crypto.kdf import ScryptKdf
from ..config import CONFIG
import base64

class KeyStore:
  """Persist public / private keys and an index file"""
  def __init__(self, resolver: PathResolver | None = None):
    self.p = resolver or PathResolver()
    self.p.ensure()
    self.kdf = ScryptKdf(CONFIG.kdf)
  
  #* -------- Index --------
  def _load_index(self) -> dict:
    return json.loads(self.p.index.read_text(encoding="utf-8"))
  
  def _save_index(self, idx: dict) -> None:
    self.p.index.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
  
  def list_keys(self) -> List[KeyInfo]:
    idx = self._load_index()
    return [KeyInfo(**k) for k in idx.get("keys", [])]
  
  def register(self, kid: str, label: str, alg: str) -> None:
    idx = self._load_index()
    idx.setdefault("keys", []).append({
      "kid": kid, "alg": alg, "label": label, "created_at": int(time.time())
    })
    self._save_index(idx)
  
  #* -------- Save / Load --------
  @staticmethod
  def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")
  
  @staticmethod
  def _b64d(s: str) -> bytes:
    """String with no padding"""
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)
  
  def write_keypair(self, kid: str, pub_pem: bytes, priv_raw_pem: bytes, passphrase_prompt: str) -> None:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import os
    
    pw = getpass(passphrase_prompt).strip()
    salt = ScryptKdf.random_salt()
    key = self.kdf.derive(pw, salt)
    aes = AESGCM(key)
    nonce = os.urandom(12)   #* 12 bytes nonce
    ct = aes.encrypt(nonce, priv_raw_pem, None)
    blob = {"v": 1, "alg": "AES-256-GCM", "salt": self._b64e(salt), "nonce": self._b64e(nonce), "ct": self._b64e(ct)}
    
    (self.p.keys / f"{kid}_pub.pem").write_bytes(pub_pem)
    (self.p.keys / f"{kid}_priv.enc").write_text(json.dumps(blob), encoding="utf-8")
  
  def _unlock_priv(self, kid: str, purpose: str) -> bytes:
    enc_path = self.p.keys / f"{kid}_priv.enc"
    pub_path = self.p.keys / f"{kid}_pub.pem"
    
    if not enc_path.exists() or not pub_path.exists():
      raise KeyNotFound(kid)
    
    blob = json.loads(enc_path.read_text(encoding="utf-8"))
    salt = self._b64d(blob["salt"])
    nonce = self._b64d(blob["nonce"])
    ct = self._b64d(blob["ct"])
    
    pw = getpass(f"Passphrase for {kid} ({purpose}): ").strip()
    key = self.kdf.derive(pw, salt)
    
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
      priv_raw_pem = AESGCM(key).decrypt(nonce, ct, None)
    except Exception as e:
      raise InvalidPassphrase from e
    
    return priv_raw_pem
  
  #* -------- Load Objects --------
  def load_public_key(self, kid: str):
    pub_pem = (self.p.keys / f"{kid}_pub.pem").read_bytes()
    return serialization.load_pem_public_key(pub_pem)
  
  def load_private_key(self, kid: str, purpose: str):
    raw = self._unlock_priv(kid, purpose)
    return serialization.load_pem_private_key(raw, password=None)
  
  
  #* --- Util ---
  @staticmethod
  def make_kid(prefix: str, pub_pem: bytes) -> str:
    h = hashlib.sha1(pub_pem).hexdigest()[:10]
    return f"{prefix}_{h}"