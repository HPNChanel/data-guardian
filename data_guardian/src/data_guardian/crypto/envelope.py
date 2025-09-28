
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from data_guardian.core.exceptions import CryptoError

MIN_RSA_KEY_BITS: Final[int] = 3072
OAEP_LABEL: Final[bytes] = b"DataGuardian-DEK"


@dataclass(slots=True)
class EnvelopePackage:
    recipient_id: str
    encrypted_key: bytes
    key_wrapping_alg: str = "RSA-OAEP-SHA256"
    

class RSAEnvelope:
    """RSA-OAEP envelope encryption with strict parameter validation"""
    
    @staticmethod
    def wrap_for_recipients(*, dek: bytes, recipients: Mapping[str, rsa.RSAPublicKey]) -> list[EnvelopePackage]:
        if not dek:
            raise CryptoError("DEK must be non-empty")
        packages: list[EnvelopePackage] = []
        for recipient_id, public_key in recipients.items():
            RSAEnvelope._validate_public_key(public_key, recipient_id)
            encrypted_key = public_key.encrypt(
                dek,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=OAEP_LABEL,
                )
            )
            packages.append(EnvelopePackage(recipient_id=recipient_id, encrypted_key=encrypted_key))
        
        return packages
    
    @staticmethod
    def unwrap(*, package: EnvelopePackage, private_key: rsa.RSAPrivateKey) -> bytes:
        RSAEnvelope._validate_private_key(private_key, package.recipient_id)
        return private_key.decrypt(
            package.encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=OAEP_LABEL,
            ),
        )

    @staticmethod
    def load_private_key(pem: bytes, passphrase: bytes | None = None) -> rsa.RSAPrivateKey:
        key = serialization.load_pem_private_key(pem, password=passphrase)
        if not isinstance(key, rsa.RSAPrivateKey):
            raise CryptoError("Expected RSA private key")
        RSAEnvelope._validate_private_key(key, "<loaded>")
        return key
    
    @staticmethod
    def _validate_public_key(public_key: rsa.RSAPublicKey, recipient_id: str) -> None:
        if public_key.key_size < MIN_RSA_KEY_BITS:
            raise CryptoError(f"Public key for {recipient_id} must be at least {MIN_RSA_KEY_BITS} bits")
    
    @staticmethod
    def _validate_private_key(private_key: rsa.RSAPrivateKey, recipient_id: str) -> None:
        if private_key.key_size < MIN_RSA_KEY_BITS:
            raise CryptoError(f"Private key for {recipient_id} must be at least {MIN_RSA_KEY_BITS} bits")
            