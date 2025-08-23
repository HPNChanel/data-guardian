# Implement the AES-256-GCM encryption engine (OOP).
from __future__ import annotations
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class AesGcm:
  """AES-256-GCM thin wrapper"""
  def __init__(self, key: bytes):
    assert len(key) == 32, "AES-256 requires 32-byte key"
    self._aes = AESGCM(key)
  
  @staticmethod
  def gen_key() -> bytes:
    return os.urandom(32)
  
  @staticmethod
  def gen_nonce() -> bytes:
    return os.urandom(12)
  
  def encrypt(self, nonce: bytes, plaintext: bytes, aad: bytes | None = None) -> bytes:
    return self._aes.encrypt(nonce, plaintext, aad)
  
  def decrypt(self, nonce: bytes, ciphertext: bytes, aad: bytes | None = None) -> bytes:
    return self._aes.decrypt(nonce, ciphertext, aad)
  