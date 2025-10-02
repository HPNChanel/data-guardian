#!/usr/bin/env python3
"""Repository invariant checks for Data Guardian."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

REQUIRED_PATHS = [
    Path("CHANGELOG.md"),
    Path("README.md"),
    Path("README_desktop.md"),
    Path("desktop_app/ui/package.json"),
    Path("desktop_app/ui/src"),
    Path("desktop_app/tauri/src-tauri/tauri.conf.json"),
    Path("scripts/build_dg_core.mjs"),
    Path("tests/desktop"),
]

FORBIDDEN_PATHS = [
    Path("index.html"),
    Path("src"),
    Path("test-results"),
    Path("ui/web-terminal"),
    Path("ui/desktop"),
]

FORBIDDEN_UI_SCRIPTS = {"dev", "preview", "serve"}


def check_required_paths() -> list[str]:
    missing = []
    for rel_path in REQUIRED_PATHS:
        if not (REPO_ROOT / rel_path).exists():
            missing.append(f"required path missing: {rel_path}")
    return missing


def check_forbidden_paths() -> list[str]:
    resurrected = []
    for rel_path in FORBIDDEN_PATHS:
        if (REPO_ROOT / rel_path).exists():
            resurrected.append(f"forbidden path present: {rel_path}")
    return resurrected


def check_ui_scripts() -> list[str]:
    package_json = REPO_ROOT / "desktop_app/ui/package.json"
    try:
        pkg = json.loads(package_json.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ["desktop_app/ui/package.json not found when validating scripts"]
    except json.JSONDecodeError as exc:
        return [f"desktop_app/ui/package.json is invalid JSON: {exc}"]

    scripts = pkg.get("scripts", {})
    offenders = sorted(FORBIDDEN_UI_SCRIPTS.intersection(scripts))
    if offenders:
        return [
            "forbidden npm scripts defined in desktop_app/ui/package.json: "
            + ", ".join(offenders)
        ]
    return []


def main() -> int:
    problems: list[str] = []
    problems.extend(check_required_paths())
    problems.extend(check_forbidden_paths())
    problems.extend(check_ui_scripts())

    if problems:
        for problem in problems:
            print(problem)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
