
from __future__ import annotations
import json, os, base64
from typing import Optional
from dataclasses import dataclass
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DEFAULT_DIR = os.environ.get("DG_KEYSTORE", os.path.expanduser("~/.data_guardian"))
SALT_SIZE = 16
NONCE_SIZE = 12

def _kdf(passphrase: bytes, salt: bytes) -> bytes:
  return Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(passphrase)

def _b64e(b: bytes) -> str:
  return base64.b64encode(b).decode("ascii")

def _b64d(s: str) -> bytes:
  return base64.b64decode(s.encode("ascii"))

@dataclass
class KeyRecord:
  name: str
  kind: str  #* rsa or ed25519
  pub: str  #* Base64
  priv_ct: str  #* base64 of AESGCM(scrypt(pass), nonce|ct)
  salt: str  #* Base64

def _aes_encrypt(key: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
  aes = AESGCM(key)
  nonce = os.urandom(NONCE_SIZE)
  ct = aes.encrypt(nonce, plaintext, None)
  return nonce, ct

def _aes_decrypt(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
  aes = AESGCM(key)
  return aes.decrypt(nonce, ciphertext, None)

class KeyStore:
  def __init__(self, root: Optional[str] = None) -> None:
    self.root = root or DEFAULT_DIR
    os.makedirs(self.root, exist_ok=True)
    self.db_path = os.path.join(self.root, "keystore.json")
    if not os.path.exists(self.db_path):
      with open(self.db_path, "w", encoding="utf-8") as f:
        json.dump({"keys": []}, f)
  
  def _load_db(self) -> dict:
    with open(self.db_path, "r", encoding="utf-8") as f:
      return json.load(f)
  
  def _save_db(self, data: dict) -> None:
    with open(self.db_path, "w", encoding="utf-8") as f:
      json.dump(data, f, indent=2)
  
  def list(self) -> list[KeyRecord]:
    db = self._load_db()
    return [KeyRecord(**k) for k in db["keys"]]

  def save_key(self, rec: KeyRecord) -> None:
    db = self._load_db()
    #* Replace if same name+kind exists
    db["keys"] = [k for k in db["keys"] if not (k["name"] == rec.name and k["kind"] == rec.kind)]
    db["keys"].append(rec.__dict__)
    self._save_db(db)
  
  def get(self, name: str, kind: str) -> Optional[KeyRecord]:
    db = self._load_db()
    for k in db["keys"]:
      if k["name"] == name and k["kind"] == kind:
        return KeyRecord(**k)
    
    return None

  def store_private(self, name: str, kind: str, public_bytes: bytes, private_pem: bytes, passphrase: bytes) -> None:
    salt = os.urandom(SALT_SIZE)
    key = _kdf(passphrase, salt)
    nonce, ct = _aes_encrypt(key, private_pem)
    payload = nonce + ct
    rec = KeyRecord(
      name=name,
      kind=kind,
      pub=_b64e(public_bytes),
      priv_ct=_b64e(payload),
      salt=_b64e(salt),
    )
    self.save_key(rec)
  
  def load_private(self, name: str, kind: str, passphrase: bytes) -> bytes:
    rec = self.get(name, kind)
    if not rec:
      raise FileNotFoundError(f"Key {name!r} ({kind}) not found")
    salt = _b64d(rec.salt)
    key = _kdf(passphrase, salt)
    payload = _b64d(rec.priv_ct)
    nonce, ct = payload[:12], payload[12:]
    pem = _aes_decrypt(key, nonce, ct)
    return pem
  
  def load_public(self, name: str, kind: str) -> bytes:
    rec = self.get(name, kind)
    if not rec:
      raise FileNotFoundError(f"Key {name!r} ({kind}) not found")
    
    return _b64d(rec.pub)
