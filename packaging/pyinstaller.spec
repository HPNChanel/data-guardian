# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building the DG Core daemon launcher."""
from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DG_CORE_SRC = PROJECT_ROOT / "dg_core" / "src"
POLICY_DIR = PROJECT_ROOT / "dg_core" / "policies"

pendulum_datas = collect_data_files("pendulum", include_py_files=False)
extra_datas = [(str(POLICY_DIR), "dg_core/policies"), *pendulum_datas]

distpath = str(PROJECT_ROOT / "dist" / "core")
workpath = str(PROJECT_ROOT / "build" / "pyinstaller")

hiddenimports = [
    "anyio._backends._asyncio",
    "pendulum.tz",
]

excludes = [
    "pytest",
    "pytest_asyncio",
    "pytest_cov",
    "hypothesis",
    "coverage",
    "mypy",
    "ruff",
    "pre_commit",
]

a = Analysis(
    [str(DG_CORE_SRC / "dg_core" / "daemon" / "server.py")],
    pathex=[str(DG_CORE_SRC)],
    binaries=[],
    datas=extra_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="dg-core",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="dg-core",
)
