# Define dataclasses or typed models (e.g., KeyInfo, DgdHeader).

from dataclasses import dataclass

from .storage.header import FileHeader as DgdHeader
from .storage.header import Recipient

__all__ = ["KeyInfo", "Recipient", "DgdHeader"]  
