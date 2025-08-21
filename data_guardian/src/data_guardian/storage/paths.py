# Manage paths and create directories as needed.
from __future__ import annotations
from pathlib import Path
from ..config import CONFIG

class PathResolver:
  """Compute and ensure paths for keystore & metadata"""
  def __init__(self, root: Path | None = None):
    self.root = (root or CONFIG.store_dir)
    self.keys = self.root / "keys"
    self.meta = self.root / "meta"
    self.index = self.root / "keys.json"
  
  def ensure(self) -> None:
    self.keys.mkdir(parents=True, exist_ok=True)
    self.meta.mkdir(parents=True, exist_ok=True)
    if not self.index.exists():
      self.index.write_text('{"keys": []}', encoding='utf-8')
