# Data Guardian

Data Guardian is a desktop-first security operations toolkit that packages encryption, key
management, and file hygiene controls into a single, offline-friendly bundle. The desktop shell
wraps the Python core with a Tauri host, while the CLI and automation hooks keep scripted
workflows close at hand.

## Table of contents
- [Overview](#overview)
- [Feature highlights](#feature-highlights)
- [Architecture](#architecture)
- [Desktop quick start](#desktop-quick-start)
- [CLI quick start](#cli-quick-start)
- [Documentation](#documentation)
- [Support and licensing](#support-and-licensing)

## Overview
Data Guardian helps security teams and incident responders keep sensitive data under control. All
cryptography happens locally, and platform-specific installers embed the Python runtime so the
application never depends on external services. You can drive the core workflows from the
cross-platform desktop shell or automate them with the Typer-based CLI.

## Feature highlights
- **Local-first desktop experience** – A Tauri host bundles the React renderer and launches the
  Python core as a child process, communicating through a local socket or Windows named pipe.
- **Policy-aware key management** – Organise encryption keys by role or group and reference them
  in policy files that the desktop and CLI expand automatically.
- **Audit-ready tooling** – Built-in health checks, log exports, and signature verification keep
  operators informed and ready for investigations.
- **Automation friendly** – The CLI mirrors desktop capabilities so scheduled jobs, CI pipelines,
  and remote responders can execute the same playbooks.

## Architecture
```
┌────────────────────┐    IPC (Unix socket / named pipe)    ┌────────────────────┐
│  Desktop shell      │  ─────────────────────────────────▶  │  Python core (dg)   │
│  (Tauri + React)    │◀───────────────────────────────────  │  Crypto + policy    │
└────────────────────┘                                       └────────────────────┘
          │                                                           │
          └────────── integrates with ───────────┐                    │
                                                 ▼                    ▼
                                       Typer CLI tooling      Local key store
```
The repository is split into three main areas:
- `desktop_app/` – React renderer assets and the Tauri host.
- `data_guardian/` – Python package that exposes the CLI and shared utilities.
- `dg_core/` – Python runtime bundle for packaging into desktop builds.

## Desktop quick start
Follow the [platform-specific install guides](docs/install_macos.md) to set up dependencies and run
Data Guardian locally. The steps below outline the happy path once prerequisites are in place.

```bash
# 1. Clone the repository
 git clone https://github.com/<your-org>/data-guardian.git
 cd data-guardian

# 2. Install JavaScript dependencies for the renderer
 npm --prefix desktop_app/ui install

# 3. Launch the desktop shell in development mode
 npm --prefix desktop_app/ui run tauri:dev
```

The dev shell bundles the Python core on demand and opens the desktop window without exposing any
network ports. Revisit the install guide for your OS when you are ready to package platform-specific
installers or embed a pre-built core runtime.

## CLI quick start
The CLI exposes the same cryptographic capabilities for scripting and automation.

```bash
# Create and activate a virtual environment (example for macOS/Linux)
python -m venv .venv
source .venv/bin/activate

# Install dependencies and enable the console entry point
pip install -r data_guardian/requirements.txt
pip install -e data_guardian

# Generate a key and encrypt a file
data-guardian keygen-rsa --label "ops-rsa"
data-guardian encrypt -i secrets.txt -o secrets.dgd --kid rsa_ops-rsa
```

Run `data-guardian --help` to browse every command. See `docs/ipc.md` for details on sockets,
named pipes, and policy expansion.

## Documentation
- [macOS install](docs/install_macos.md)
- [Windows install](docs/install_windows.md)
- [Linux install](docs/install_linux.md)
- [Troubleshooting](docs/troubleshooting.md)
- [User guide](docs/user_guide.md)
- [Contributing](docs/contributing.md)
- [Desktop release process](docs/release.md)

## Support and licensing
- Health checks: `data-guardian selftest` and `data-guardian doctor`
- Issues: file tickets with the Core Security Engineering team
- License: MIT
