#!/usr/bin/env python3
"""Build the PyInstaller bundle for DG Core."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO_ROOT / "packaging" / "pyinstaller.spec"
DIST_DIR = REPO_ROOT / "dist" / "core"
BUILD_DIR = REPO_ROOT / "build" / "pyinstaller"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the DG Core standalone bundle")
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Skip removing previous build artefacts before running PyInstaller",
    )
    parser.add_argument(
        "pyinstaller_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments forwarded to PyInstaller (prefix with --)",
    )
    return parser.parse_args()


def clean() -> None:
    for path in (DIST_DIR, BUILD_DIR):
        if path.exists():
            shutil.rmtree(path)


def run_pyinstaller(extra_args: list[str]) -> None:
    if not SPEC_PATH.is_file():
        raise SystemExit(f"Spec file not found: {SPEC_PATH}")

    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC_PATH), *extra_args]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def main() -> None:
    args = parse_args()
    if not args.no_clean:
        clean()
    extra_args = args.pyinstaller_args or []
    run_pyinstaller(extra_args)
    print(f"Bundle written to {DIST_DIR}")


if __name__ == "__main__":
    main()
