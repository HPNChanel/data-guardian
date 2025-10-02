#!/usr/bin/env python3
"""Automated end-to-end verification for Data Guardian."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
CLI_MANIFEST = ROOT / "e2e" / "rpc_client" / "Cargo.toml"
FIXTURES = ROOT / "e2e" / "fixtures"


class E2EError(RuntimeError):
    """Raised when the end-to-end test suite fails."""


def log(msg: str) -> None:
    print(f"[e2e] {msg}")


def resolve_artifacts_dir(path: Optional[Path]) -> tuple[Path, Optional[tempfile.TemporaryDirectory]]:
    if path is not None:
        path.mkdir(parents=True, exist_ok=True)
        return path, None
    temp_dir = tempfile.TemporaryDirectory(prefix="dg-e2e-")
    return Path(temp_dir.name), temp_dir


def launch_desktop_headless() -> bool:
    """Attempt to launch the desktop app in headless mode.

    The current CI environment lacks a display server, so we always fall back to
    the daemon/CLI path unless DG_E2E_USE_DESKTOP is explicitly set.
    """

    if os.environ.get("DG_E2E_USE_DESKTOP") == "1":
        log("Desktop mode requested but not implemented in automated environment")
    return False


def platform_endpoint(artifacts: Path) -> tuple[List[str], Dict[str, Any]]:
    if os.name == "nt":
        pipe_name = f"data_guardian_e2e_{os.getpid()}"
        return ["--pipe", pipe_name], {"pipe": pipe_name}
    socket_path = artifacts / "dg-core.sock"
    return ["--socket", str(socket_path)], {"socket": socket_path}


def start_daemon(endpoint_kwargs: Dict[str, Any], log_path: Path) -> subprocess.Popen[Any]:
    cmd = [sys.executable, "-m", "dg_core.daemon.server"]
    if "socket" in endpoint_kwargs:
        cmd.extend(["--socket", str(endpoint_kwargs["socket"])])
    if "pipe" in endpoint_kwargs:
        cmd.extend(["--pipe", str(endpoint_kwargs["pipe"])])

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")
    log("Starting dg_core daemon: %s" % " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    setattr(proc, "_dg_log_handle", log_file)
    return proc


def run_cli(endpoint_args: List[str], command: List[str], *, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    cargo_cmd = [
        "cargo",
        "run",
        "--manifest-path",
        str(CLI_MANIFEST),
        "--quiet",
        "--",
        *endpoint_args,
        *command,
    ]
    log(f"Running CLI: {' '.join(cargo_cmd)}")
    result = subprocess.run(
        cargo_cmd,
        cwd=str(ROOT),
        text=True,
        capture_output=capture_output,
        check=True,
    )
    return result


def call_cli(endpoint_args: List[str], method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = json.dumps(params or {})
    result = run_cli(endpoint_args, ["call", method, "--params", payload])
    stdout = result.stdout.strip()
    if not stdout:
        raise E2EError(f"No output received from CLI for method {method}")
    line = stdout.splitlines()[-1]
    log(f"Received response: {line}")
    try:
        return json.loads(line)
    except json.JSONDecodeError as exc:
        raise E2EError(f"Invalid JSON from CLI for {method}: {line}") from exc


def wait_for_daemon(endpoint_args: List[str], timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = call_cli(endpoint_args, "core.ping")
        except subprocess.CalledProcessError:
            time.sleep(0.25)
            continue
        except E2EError:
            time.sleep(0.25)
            continue
        else:
            if response.get("result"):
                return
            # Legacy format
            if response.get("ok"):
                return
            time.sleep(0.25)
    raise E2EError("Timed out waiting for daemon readiness")


def tail_logs(endpoint_args: List[str], artifacts: Path, duration_ms: int = 6000) -> tuple[subprocess.Popen[Any], Path]:
    log_path = artifacts / "core_logs.jsonl"
    log_file = log_path.open("w", encoding="utf-8")
    cmd = [
        "tail-logs",
        "--duration-ms",
        str(duration_ms),
        "--max-events",
        "32",
    ]
    proc = subprocess.Popen(
        [
            "cargo",
            "run",
            "--manifest-path",
            str(CLI_MANIFEST),
            "--quiet",
            "--",
            *endpoint_args,
            *cmd,
        ],
        cwd=str(ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    setattr(proc, "_dg_log_handle", log_file)
    return proc, log_path


def collect_log_notifications(log_path: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not log_path.exists():
        return entries
    for raw in log_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if payload.get("method") == "core.log":
            entries.append(payload)
    return entries


def write_report(artifacts: Path, lines: List[str]) -> None:
    report = artifacts / "report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def close_log_handle(proc: subprocess.Popen[Any]) -> None:
    handle = getattr(proc, "_dg_log_handle", None)
    if handle is not None:
        try:
            handle.close()
        except Exception:
            pass


def run_tests(artifacts: Path) -> None:
    endpoint_args, endpoint_kwargs = platform_endpoint(artifacts)
    daemon_log = artifacts / "daemon.log"
    daemon = start_daemon(endpoint_kwargs, daemon_log)
    tail_proc: Optional[subprocess.Popen[Any]] = None
    log_path: Optional[Path] = None

    try:
        wait_for_daemon(endpoint_args)
        log("Daemon is ready")

        tail_proc, log_path = tail_logs(endpoint_args, artifacts)
        time.sleep(0.5)

        sample_path = FIXTURES / "sample.txt"
        policy_path = FIXTURES / "test_policy.yaml"
        sample_content = sample_path.read_text(encoding="utf-8")

        ping = call_cli(endpoint_args, "core.ping")
        if ping.get("result"):
            result_payload = ping["result"]
        else:
            result_payload = ping
        if not result_payload.get("ok"):
            raise E2EError("core.ping did not report ok status")

        load_policy = call_cli(endpoint_args, "core.load_policy", {"path": str(policy_path)})
        policy_name = load_policy.get("result", {}).get("policy", {}).get("name")
        if policy_name is None:
            policy_name = load_policy.get("policy", {}).get("name")
        if policy_name != "e2e-test":
            raise E2EError("Policy name mismatch")

        scan = call_cli(endpoint_args, "core.scan_path", {"path": str(sample_path)})
        detections = scan.get("result", {}).get("detections")
        if detections is None:
            detections = scan.get("detections")
        if not detections:
            raise E2EError("Scanner returned no detections for fixture")

        redacted_output = artifacts / "redacted.txt"
        redact = call_cli(
            endpoint_args,
            "core.redact_file",
            {
                "path": str(sample_path),
                "policy_path": str(policy_path),
                "output_path": str(redacted_output),
            },
        )
        redacted_path = (
            redact.get("result", {}).get("written_to")
            or redact.get("written_to")
        )
        if not redacted_path:
            raise E2EError("Redaction response missing output path")
        if Path(redacted_path).read_text(encoding="utf-8").count("4111"):
            raise E2EError("Redacted output still contains sensitive value")

        test_policy = call_cli(
            endpoint_args,
            "core.test_policy",
            {"text": sample_content, "policy_path": str(policy_path)},
        )
        output = test_policy.get("result", {}).get("output") or test_policy.get("output")
        if output is None or "jane.doe@example.com" in output:
            raise E2EError("Policy test did not redact email address")

        try:
            shutdown_response = call_cli(endpoint_args, "core.shutdown")
        except subprocess.CalledProcessError:
            log("core.shutdown request failed; terminating daemon directly")
            daemon.terminate()
        else:
            error_payload = shutdown_response.get("error")
            if error_payload and error_payload.get("code") == -32601:
                log("core.shutdown not available; terminating daemon directly")
                daemon.terminate()
            else:
                log("Shutdown request accepted by daemon")

        log("Waiting for daemon to exit")
        try:
            daemon.wait(timeout=15)
        except subprocess.TimeoutExpired:
            log("Daemon did not exit gracefully; forcing termination")
            daemon.terminate()
            daemon.wait(timeout=5)
        finally:
            close_log_handle(daemon)

        if tail_proc is not None:
            try:
                tail_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                tail_proc.terminate()
                tail_proc.wait(timeout=5)
            finally:
                close_log_handle(tail_proc)

        if log_path is None:
            raise E2EError("Log stream path was not created")

        notifications = collect_log_notifications(log_path)
        if not notifications:
            raise E2EError("No log notifications captured from tail_logs")

        summary_lines = [
            "# Data Guardian E2E Report",
            "",
            f"* core.ping -> ok (version={result_payload.get('version')})",
            f"* core.load_policy -> policy '{policy_name}' loaded",
            f"* core.scan_path -> {len(detections)} detections",
            f"* core.redact_file -> output saved to {redacted_path}",
            f"* core.test_policy -> produced redacted output of length {len(output)}",
            f"* core.tail_logs -> captured {len(notifications)} log events",
        ]
        write_report(artifacts, summary_lines)
        log("E2E tests completed successfully")
    except Exception:
        if tail_proc is not None:
            with contextlib.suppress(Exception):
                tail_proc.terminate()
                tail_proc.wait(timeout=5)
                close_log_handle(tail_proc)
        daemon.terminate()
        try:
            daemon.wait(timeout=5)
        except subprocess.TimeoutExpired:
            daemon.kill()
        finally:
            close_log_handle(daemon)
        raise


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Data Guardian end-to-end checks")
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Directory for logs, reports, and other outputs",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    artifacts_dir, temp_dir = resolve_artifacts_dir(args.artifacts_dir)
    log(f"Writing artifacts to {artifacts_dir}")
    try:
        if not launch_desktop_headless():
            run_tests(artifacts_dir)
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


if __name__ == "__main__":
    main()
