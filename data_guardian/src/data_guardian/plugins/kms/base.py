
class KMSClient:
    """A minimal interface for external key managers/HSMs
    
    This is a stub to demonstrate how to integrate non-file keystores
    """
    
    def get_public_key(self, name: str, kind: str) -> bytes:
        raise NotImplementedError
    
    def wrap_key(self, name: str, kek: bytes) -> bytes:
        """Wrap a data key using the KMS-managed RSA/ECC key"""
        raise NotImplementedError
