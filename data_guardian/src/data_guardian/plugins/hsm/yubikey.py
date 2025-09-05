class YubiKeyHSM:
    """Stub for YubiKey/HSM integration.

    Methods mirror KMS-like operations for wrapping/unwrapping keys
    using hardware-backed keys.
    """

    def list_slots(self):
        raise NotImplementedError

    def get_public_key(self, slot: str) -> bytes:
        raise NotImplementedError

    def wrap_key(self, slot: str, data: bytes) -> bytes:
        raise NotImplementedError

    def unwrap_key(self, slot: str, ct: bytes) -> bytes:
        raise NotImplementedError

