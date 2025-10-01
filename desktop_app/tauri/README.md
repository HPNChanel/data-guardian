# Data Guardian Desktop Shell

The Tauri shell embeds the DG Core Python runtime and exposes a secure desktop experience without opening any external network ports. Communication between the Rust shell and the Python core is intentionally restricted to local-only transports:

- **macOS** – Unix domain socket at `~/Library/Application Support/DataGuardianDesktop/ipc/dg-core.sock`
- **Linux** – Unix domain socket at `/home/$USER/.local/share/DataGuardianDesktop/ipc/dg-core.sock`
- **Windows** – Named pipe `\\.\pipe\data_guardian_core`

The default build does **not** enable TCP listeners. A TCP JSON-RPC endpoint remains behind the optional `debug-tcp-fallback` Cargo feature for development troubleshooting. Do not ship builds with that feature enabled.

## Runtime layout

The packaged Python runtime is copied into `resources/dg_runtime/` by `scripts/build_dg_core.mjs`. The launcher scripts call `python -m dg_core.cli.main` so the full standard import system is available inside the embedded interpreter.

## Development lifecycle

1. Install Node.js (18+), Rust (stable), and Python 3.10+.
2. Build the UI with `npm --prefix ../ui install` followed by `npm --prefix ../ui run build`.
3. Prepare the Python runtime with `node ../../scripts/build_dg_core.mjs`.
4. Run the Tauri shell with `cargo tauri dev` from `src-tauri/`.

See [`docs/ipc.md`](../../docs/ipc.md) for socket troubleshooting tips and firewall guidance.
