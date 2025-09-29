
import base64


def b64d(value: str) -> bytes:
    """URL-safe base64 decode that tolerates missing padding"""
    pad = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + pad).encode("ascii"))
