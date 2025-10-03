"""Typer-based command line interface for DG Core."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import typer

from ..config import AppConfig, load_config
from ..logging import configure_logging
from ..policy import policy_from_path
from ..policy.engine import PolicyEngine
from ..redactor.engines import RedactionEngine
from ..scanner import ScannerConfig, scan_text

app = typer.Typer(help="DG Core command line interface")


@app.callback()
def main(ctx: typer.Context, config: Optional[Path] = typer.Option(None, "--config", metavar="PATH")) -> None:
    ctx.obj = load_config(config)
    configure_logging(ctx.obj.logging.normalized_level())


def _guard_policy_only(feature: str) -> AppConfig:
    ctx = typer.get_current_context()
    config: AppConfig = ctx.obj
    if getattr(config.network, "policy_only_offline", False):
        typer.echo(f"{feature} is unavailable in policy-only offline mode", err=True)
        raise typer.Exit(code=2)
    return config


@app.command()
def scan(
    path: Path = typer.Argument(..., exists=True, readable=True),
    detector: Optional[str] = typer.Option(None, "--detector", help="Restrict to detector name or prefix"),
    max_results: Optional[int] = typer.Option(None, "--max-results", help="Cap detections"),
) -> None:
    _guard_policy_only("Scanning")
    data = path.read_bytes()
    config = ScannerConfig(enabled=[detector] if detector else None, max_detections=max_results)
    detections = scan_text(data, config=config)
    typer.echo(json.dumps([asdict(det) for det in detections], ensure_ascii=False, indent=2))


@app.command()
def redact(
    input_path: Path = typer.Argument(..., exists=True, readable=True),
    output: Path = typer.Option(..., "-o", "--output", help="Write redacted output here"),
    policy: Path = typer.Option(..., "--policy", help="Policy document for redaction"),
) -> None:
    _guard_policy_only("Redaction")
    content = input_path.read_bytes()
    policy_doc = policy_from_path(policy)
    engine = PolicyEngine(policy_doc)
    redactor = RedactionEngine(engine)
    detections = scan_text(content)
    redacted, _segments = redactor.redact(content, detections)
    if isinstance(redacted, bytes):
        output.write_bytes(redacted)
    else:
        output.write_text(redacted, encoding="utf-8")
    typer.echo(f"Redacted output written to {output}")


@app.command()
def serve(
    config: Optional[Path] = typer.Option(None, "--config", help="Override config path"),
) -> None:
    from ..ipc.server import IPCServer

    app_config: AppConfig = load_config(config)
    configure_logging(app_config.logging.normalized_level())
    server = IPCServer(app_config)
    asyncio.run(server.serve_forever())


@app.command()
def policy_set(
    source: Path = typer.Argument(..., exists=True, readable=True),
    destination: Path = typer.Option(Path.cwd() / "policies" / "active.yaml", "--destination", help="Destination policy path"),
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())
    typer.echo(f"Policy copied to {destination}")


@app.command()
def policy_show(policy: Path = typer.Option(..., "--policy", help="Policy to inspect")) -> None:
    document = policy_from_path(policy)
    typer.echo(document.model_dump_json(indent=2))


@app.command()
def version() -> None:
    from ..version import __version__

    typer.echo(__version__)


if __name__ == "__main__":  # pragma: no cover
    app()