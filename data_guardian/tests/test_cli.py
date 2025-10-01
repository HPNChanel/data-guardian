from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("typer")


def _run_cli(*args: str, input_data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    command = [sys.executable, "-m", "data_guardian.cli", *args]
    env = os.environ.copy()
    module_root = Path(__file__).resolve().parents[1] / "src"
    env["PYTHONPATH"] = (
        f"{module_root}{os.pathsep}{env['PYTHONPATH']}"
        if env.get("PYTHONPATH")
        else str(module_root)
    )
    return subprocess.run(
        command,
        check=True,
        input=input_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def test_cli_reports_version() -> None:
    result = _run_cli("--version")
    assert result.stdout.decode("utf-8").strip().startswith("data-guardian")


def test_cli_scan_round_trip(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("Contact me at alice@example.com", encoding="utf-8")
    result = _run_cli("scan", "-i", str(sample))
    payload = json.loads(result.stdout.decode("utf-8"))
    assert isinstance(payload, list)
    assert payload, "expected detections from sample text"
