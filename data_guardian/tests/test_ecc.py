from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization
from data_guardian.crypto.ecc import X25519KeyPair
from data_guardian.crypto.symmetric import gen_key_for


def test_x25519_wrap_unwrap():
    receiver = x25519.X25519PrivateKey.generate()
    cek = gen_key_for("AESGCM")
    wrap = X25519KeyPair.wrap_cek_for_recipient(receiver.public_key(), cek)
    recovered = X25519KeyPair.unwrap_cek(receiver, wrap)
    assert recovered == cek

