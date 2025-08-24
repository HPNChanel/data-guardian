# Implement RSA-OAEP keypair operations (OOP).
from __future__ import annotations
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

class RsaKeyPair:
  """RSA-3072 keypair utilities"""
  def __init__(self, private=None, public=None):
    self._priv = private
    self._pub = public or (private.public_key() if private else None)
  
  @staticmethod
  def generate(bits: int = 3072) -> "RsaKeyPair":
    priv = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    return RsaKeyPair(private=priv)
  
  def public_pem(self) -> bytes:
    return self._pub.public_bytes(
      encoding=serialization.Encoding.PEM,
      format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
  
  def private_pem_pkcs8(self) -> bytes:
    return self._priv.private_bytes(
      encoding=serialization.Encoding.PEM,
      format=serialization.PrivateFormat.PKCS8,
      encryption_algorithm=serialization.NoEncryption()
    )
  
  def wrap_key(self, session_key: bytes) -> bytes:
    return self._pub.encrypt(
      session_key,
      padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                  algorithm=hashes.SHA256(), label=None)
    )
  
  def unwrap_key(self, wrapped: bytes) -> bytes:
    return self._priv.decrypt(
      wrapped,
      padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                  algorithm=hashes.SHA256(), label=None)
    )
  