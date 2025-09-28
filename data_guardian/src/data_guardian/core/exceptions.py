
from __future__ import annotations

"""Central exception hierarchy"""
class DataGuardianError(Exception):
    """Base exception for all failures"""


class CryptoError(DataGuardianError):
    """Raised for cryptographic misuse or integrity failures"""


class PolicyError(DataGuardianError):
    """Raise when policy evaluation denies an operation"""
    

class AuditError(DataGuardianError):
    """Raised when audit logging cannot be persisted safely"""
