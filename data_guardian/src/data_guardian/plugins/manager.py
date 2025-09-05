from __future__ import annotations

import importlib
from typing import Any


def load_plugin(path: str, class_name: str) -> Any:
    """Dynamically load a plugin class given module path and class name.

    Example: load_plugin('data_guardian.plugins.kms.base', 'KMSClient')
    """
    mod = importlib.import_module(path)
    return getattr(mod, class_name)


def load_entrypoint(name: str) -> Any:
    """Placeholder for future entrypoints-based loading."""
    return importlib.import_module(name)

