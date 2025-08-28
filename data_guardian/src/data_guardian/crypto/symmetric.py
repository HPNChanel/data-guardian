
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AES_KEY_SIZE = 32  #* 256-bit
NONCE_SIZE = 12

def gen_key() -> bytes:
  return os.urandom(AES_KEY_SIZE)
  
def encrypt(key: bytes, plaintext: bytes, aad: bytes = b"")-> tuple[bytes, bytes]:
  aesgcm = AESGCM(key)
  nonce = os.urandom(NONCE_SIZE)
  ct = aesgcm.encrypt(nonce, plaintext, aad)
  return nonce, ct
  
def decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes:
  aesgcm = AESGCM(key)
  return aesgcm.decrypt(nonce, ciphertext, aad) 
