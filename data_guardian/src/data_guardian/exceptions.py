# Define custom exceptions with clear names.
class DataGuardianError(Exception):
  """Base exception for Data Guardian"""

class KeyNotFound(DataGuardianError):
  """Raised when a key id cannot be found in keystore."""

class InvalidPassphrase(DataGuardianError):
  """Raised when passphrase cannot decrypt a private key"""

class InvalidDgdFile(DataGuardianError):
  """Raised when input .dgd file is malformed"""
  
