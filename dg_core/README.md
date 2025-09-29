# DG Core

DG Core provides high performance scanning, redaction, and policy enforcement with a local IPC server for secure integrations.

## Features
- Pluggable detectors for PII, secrets, and configuration leaks
- Policy-driven redaction strategies with allowlists and precedence
- Async JSON-RPC server with Unix domain socket, Windows named pipe, and TCP fallback
- Typer-based CLI for scanning, redaction, policy management, and server control
- Structured logging with `structlog`
- pytest test suite with unit, integration, property, and benchmark coverage

## Getting Started
1. Install dependencies with Poetry: `poetry install`
2. Activate the shell: `poetry shell`
3. Run the CLI: `dg scan sample.txt`
4. Start the server: `dg serve`

## Configuration
Default configuration lives in `.dg/config.yaml` and controls logging level, IPC transport selection, and network allowances.

## Policies
Policies are defined in YAML/JSON and validated by Pydantic. See `policies/default.yaml` for an example.

## Tests
Run tests with `poetry run pytest`. Benchmarks are isolated with the `bench` marker: `poetry run pytest -m bench`.