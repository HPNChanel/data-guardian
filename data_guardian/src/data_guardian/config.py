# Configuration for the application (e.g., storage directory, KDF parameters).

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path  #* Support for working with file and directories base on OOP

DEFAULT_APP_ROOT = Path(__file__).resolve.parents[2]  #* Project root
#* parents[0]: current directory
#* parents[1]: parent directory
#* parents[2]: grand-parent directory

DEFAULT_STORE = DEFAULT_APP_ROOT / "dg_store"

@dataclass(frozen=True)  #* Make all object `immutable`
class KdfConfig:
  n: int = 2**15  #* CPU Cost Parameter
  r: int = 8  #* Block size
  p: int = 1  #* Parallelization
  length: int = 32  #* Size of key
  

@dataclass(frozen=True)
class AppConfig:
  store_dir: Path = DEFAULT_STORE
  kdf: KdfConfig = KdfConfig()

CONFIG = AppConfig()