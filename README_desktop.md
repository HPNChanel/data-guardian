# Data Guardian Desktop

This repository hosts the desktop-only Data Guardian experience. The desktop shell embeds the Python runtime, exposes a local-only IPC bridge, and never opens an HTTP endpoint for terminal access.

## Project layout

- `desktop_app/ui/` &mdash; React + Vite renderer packaged for Tauri 2.
- `desktop_app/tauri/` &mdash; Rust host responsible for process management, settings, and IPC.
- `scripts/build_dg_core.mjs` &mdash; Copies the packaged Python runtime into the Tauri resources directory.

## Prerequisites

- Rust toolchain with `cargo`
- Node.js 18+
- Python 3.11 for packaging DG Core

## Install dependencies

```bash
npm --prefix desktop_app/ui install
```

The Tauri CLI is installed as a dev dependency, so the npm scripts are sufficient for local development.

## Development workflow

```bash
npm --prefix desktop_app/ui run tauri:dev
```

The dev script builds assets in-memory and launches the shell without exposing any web server. All renderer assets are served through Tauri's asset protocol.

## Building installers

```bash
npm --prefix desktop_app/ui run build
node scripts/build_dg_core.mjs
cargo tauri build --manifest-path desktop_app/tauri/src-tauri/Cargo.toml
```

Build artefacts are emitted under `desktop_app/tauri/src-tauri/target/release/bundle/` for the current platform.

## Security posture

- IPC is restricted to Unix domain sockets (macOS/Linux) or a Windows named pipe.
- No HTTP routes or web-hosted terminal components are shipped.
- Desktop builds bundle the Python runtime locally; no external downloads are required at runtime.
