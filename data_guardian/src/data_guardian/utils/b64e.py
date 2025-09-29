
import base64

def b64e(data: bytes) -> str:
    """URL-safe base64 encode without padding"""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")
