# Implement RSA-OAEP keypair operations (OOP).
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ed25519
from cryptography.hazmat.primitives import serialization, hashes

def gen_rsa() -> rsa.RSAPrivateKey:
  return rsa.generate_private_key(public_exponent=65537, key_size=3072)

def rsa_public_bytes(priv: rsa.RSAPrivateKey) -> bytes:
  return priv.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
  )

def rsa_private_bytes(priv: rsa.RSAPrivateKey, passphrase: bytes | None = None) -> bytes:
  if passphrase:
    encryption = serialization.BestAvailableEncryption(passphrase)
  else:
    encryption = serialization.NoEncryption()
  
  return priv.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    encryption,
  )

def rsa_load_private(pem: bytes, passphrase: bytes | None = None) -> rsa.RSAPrivateKey:
  return serialization.load_pem_private_key(pem, password=passphrase)

def rsa_encrypt(pub, data: bytes) -> bytes:
  return pub.encrypt(
    data, 
    padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
  )

def rsa_decrypt(priv, ct: bytes) -> bytes:
  return priv.decrypt(
    ct,
    padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
  )

#* Ed25519
def gen_ed25519() -> ed25519.Ed25519PrivateKey:
  return ed25519.Ed25519PrivateKey.generate()

def ed25519_public_bytes(priv: ed25519.Ed25519PrivateKey) -> bytes:
  return priv.public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw
  )

def ed25519_private_bytes(priv: ed25519.Ed25519PrivateKey, passphrase: bytes | None = None) -> bytes:
  if passphrase:
    encryption = serialization.BestAvailableEncryption(passphrase)
  else:
    encryption = serialization.NoEncryption()
  
  return priv.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    encryption,
  )

def ed25519_load_private(pem: bytes, passphrase: bytes | None = None) -> ed25519.Ed25519PrivateKey:
  return serialization.load_pem_private_key(pem, password=passphrase)

def sign(priv: ed25519.Ed25519PrivateKey, data: bytes) -> bytes:
  return priv.sign(data)

def verify(pub, sig: bytes, data: bytes) -> None:
  pub.verify(sig, data)
