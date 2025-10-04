# Data Guardian Desktop

The desktop application ships a Rust controller over a Tauri host and bundles the Data Guardian core engine. The UI interacts
exclusively with the `Controller` facade while encryption, policy enforcement, and telemetry are handled by the shared `dg_core`
crate.

## Project layout

- `dg_core/` &mdash; Rust library exposing the async Data Guardian facade and policy/crypto primitives.
- `desktop_app/tauri/` &mdash; Rust desktop host (controller, configuration, telemetry, and Tauri shell).
- `desktop_app/ui/` &mdash; React + Vite renderer packaged for Tauri.
- `packaging/assets/` &mdash; Default configuration and policy templates copied into release bundles.
- `scripts/dev_all.sh` &mdash; End-to-end build pipeline producing preview installers and smoke testing the bundle.

## Prerequisites

- Rust toolchain (`rustup default stable`, `cargo`, `clippy`, `rustfmt`).
- Node.js 18+ (for renderer assets and the Tauri CLI invoked through npm).
- Python 3.11 for packaging the legacy DG Core runtime (still referenced by the existing build script).

## Local development

1. Install UI dependencies once:
   ```bash
   npm --prefix desktop_app/ui ci
   ```
2. Launch the desktop shell in development mode:
   ```bash
   npm --prefix desktop_app/ui run tauri:dev
   ```
   The command recompiles the Rust host on change and streams Vite assets to the Tauri window.

### Running the controller directly

The Rust host exposes a CLI-friendly entry point. To boot the application with the default configuration and open the UI:
```bash
cargo run -p desktop_app
```

## Configuration

The desktop host resolves configuration in the following order:

1. Environment variables:
   - `DG_PROFILE` &mdash; Overrides the active profile (`dev` by default).
   - `DG_TELEMETRY` &mdash; `true`/`false` to toggle OTLP export (defaults to disabled).
   - `DG_DATA_DIR` &mdash; Explicit data directory for keys, logs, and policy cache.
2. File config located at:
   - Windows: `%APPDATA%/DataGuardian/config.toml`
   - macOS/Linux: `${HOME}/.config/data_guardian/config.toml`
3. Platform defaults resolving to `${HOME}/.local/share/data_guardian` (Linux/macOS) or `%APPDATA%/DataGuardian` (Windows).

Sample configuration and policy templates are published under `packaging/assets/` and copied into preview builds.

## Telemetry and diagnostics

- When telemetry is disabled, structured logs are written to `<data_dir>/logs/desktop.log` with rotation handled by the
  `tracing-appender` non-blocking writer.
- When telemetry is enabled, the host initialises an OTLP-capable pipeline (extend `telemetry::init` with exporter wiring as
  infrastructure becomes available).
- The Tauri command `tail_logs` streams the most recent log lines into the Diagnostics panel.

## Testing

The workspace enables a full suite of checks:

```bash
cargo fmt --check
cargo clippy --workspace -D warnings
cargo test --workspace --all-features
```

Integration coverage includes:

- `dg_core` unit tests for policy parsing and crypto primitives.
- `desktop_app` controller tests covering policy denial and round-trip encryption.
- E2E flows under `e2e/rpc_client/tests` validating happy path, policy denial, and corrupt envelope behaviour.
- A workspace-level smoke test (`tests/desktop_smoke.rs`) that exercises boot → encrypt → decrypt → shutdown using the controller.

## Packaging

The consolidated build script reproduces the release pipeline locally:

```bash
./scripts/dev_all.sh
```

The script performs the following steps:

1. Builds the renderer bundle.
2. Packages the Python runtime resources.
3. Builds the Tauri application via `npx tauri build`.
4. Builds the Rust binary (`cargo build -p desktop_app --release`).
5. Copies default configuration/policy assets into `dist/release/preview/assets/`.
6. Executes the Node smoke test harness.

Release artefacts land under `dist/release/preview/`. Sign binaries on each platform following the guides in `packaging/<platform>/`.
Add OTLP credentials and KMS/HSM endpoints through the runtime configuration or environment variables &mdash; secrets must never be
checked into the repository.

## Known issues

- OTLP exporter wiring is stubbed in `telemetry::init`; integrate with the production collector before enabling telemetry in
  production builds.
- The legacy bridge modules remain in the crate for backwards compatibility but are no longer used by the controller. They will be
  removed once the UI migrates entirely to the new flow.
