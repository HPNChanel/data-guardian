# Implement the Scrypt KDF with parameterization.
from __future__ import annotations
import os
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from ..config import KdfConfig

class ScryptKdf:
  def __init__(self, cfg: KdfConfig):
    self.cfg = cfg
  
  @staticmethod
  def random_salt() -> bytes:
    return os.urandom(16)
  
  def derive(self, passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=self.cfg.length, n=self.cfg.n, r=self.cfg.r, p=self.cfg.p)
    return kdf.derive(passphrase.encode("utf-8"))
