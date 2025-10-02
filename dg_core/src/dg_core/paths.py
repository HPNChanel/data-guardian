"""Shared filesystem path helpers for DG Core."""
from __future__ import annotations

import sys
from pathlib import Path

from platformdirs import PlatformDirs

_APP_NAME = "Data Guardian"
_LINUX_APP_NAME = "data-guardian"


def runtime_config_dir() -> Path:
    """Return the per-user runtime configuration directory."""
    if sys.platform == "win32":
        dirs = PlatformDirs(appname=_APP_NAME, appauthor=None, roaming=True)
    elif sys.platform == "darwin":
        dirs = PlatformDirs(appname=_APP_NAME, appauthor=None, roaming=True)
    else:
        dirs = PlatformDirs(appname=_LINUX_APP_NAME, appauthor=None, roaming=False)
    return Path(dirs.user_config_path)


def default_unix_socket_path() -> Path:
    """Return the default Unix domain socket location."""
    return runtime_config_dir() / "ipc" / "dg-core.sock"


def default_named_pipe() -> str:
    """Return the default Windows named pipe."""
    return r"\\.\pipe\data_guardian_core"
