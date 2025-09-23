
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

_STORE_ENV = "DG_STORE_DIR"


def _default_store() -> Path:
    value = os.getenv(_STORE_ENV)
    if value:
        return Path(value).expanduser()
    
    return Path.home() / ".data_guardian"
