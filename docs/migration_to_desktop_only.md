# Migration Plan: Desktop-Only Data Guardian

> Goal: remove the web-hosted terminal surface and ship a signed, installable desktop application for Windows, macOS, and Linux while leaving the Python DG Core logic intact.

## Repository Map (current state)
- [ ] Validate that the repo currently matches the following layout before applying changes:
  ```text
  .
  ├── README.md
  ├── data_guardian/
  │   ├── pyproject.toml
  │   ├── requirements.txt
  │   ├── src/data_guardian/
  │   └── tests/
  ├── dg_core/
  │   ├── pyproject.toml
  │   ├── src/dg_core/
  │   └── tests/
  ├── index.html                 # Vite entry for web-hosted terminal build (to remove)
  ├── scripts/build_dg_core.mjs   # Copies DG Core into Tauri resources
  ├── src/                        # React + xterm.js web bundle (to replace)
  ├── src-tauri/                  # Tauri shell (Rust)
  │   ├── Cargo.toml
  │   ├── tauri.conf.json
  │   └── src/
  ├── test-results/               # Playwright artefacts for web UI (to remove)
  └── tests/ui/                   # Playwright specs for web terminal (to remove)
  ```

## Identify & Remove Web-Hosted Terminal Assets
- [ ] Delete the web-hosted entrypoint and dev artefacts:
  ```bash
  rm index.html
  rm -rf src/
  rm -rf tests/ui/
  rm -rf test-results/
  ```
- [ ] Remove any web deployment references in documentation (e.g., `README.md` sections pointing to browser usage).

## Desktop Application Restructure
- [ ] Create a dedicated desktop workspace:
  ```bash
  mkdir -p desktop_app/ui
  mkdir -p desktop_app/tauri
  ```
- [ ] Move the existing Tauri project under `desktop_app/tauri/` and update paths:
  ```bash
  git mv src-tauri desktop_app/tauri
  ```
- [ ] Create a fresh Vite+React (or Svelte/solid) project scoped for desktop-only usage under `desktop_app/ui/`:
  ```bash
  cd desktop_app/ui
  npm create vite@latest . -- --template react-ts
  ```
- [ ] Re-implement the terminal panel locally (reuse logic from `src/components/Terminal.tsx` but ensure it only runs within Tauri’s context, no external hosting or dev server exposure).
- [ ] Wire IPC calls via Tauri commands instead of any HTTP bridge exposed by the web build.
- [ ] Update import paths and build outputs so that `desktop_app/ui/dist/` is consumed by Tauri.

### Updated directory tree (target)
- [ ] Ensure the final top-level layout matches:
  ```text
  .
  ├── README.md
  ├── docs/
  │   └── migration_to_desktop_only.md
  ├── data_guardian/
  ├── dg_core/
  ├── desktop_app/
  │   ├── ui/                    # Vite desktop-only frontend
  │   │   ├── package.json
  │   │   ├── tsconfig.json
  │   │   ├── src/
  │   │   └── public/
  │   └── tauri/
  │       ├── Cargo.toml
  │       ├── tauri.conf.json
  │       └── src/
  ├── packaging/
  │   ├── README.md
  │   ├── macos/
  │   │   └── SIGNING.md
  │   ├── windows/
  │   │   ├── SIGNING.md
  │   │   └── wix/ (heat candle placeholders)
  │   └── linux/
  │       └── SIGNING.md
  ├── scripts/
  │   └── build_dg_core.mjs
  └── tests/
      └── desktop/               # Replace Playwright specs with desktop smoke tests
  ```

## IPC & Runtime Strategy
- [ ] Update `desktop_app/tauri/src/process/mod.rs` to eliminate TCP fallback by default (keep the code path guarded behind a feature flag for debugging only). Prefer:
  - Unix domain sockets at `~/Library/Application Support/DataGuardianDesktop/ipc/dg-core.sock` (macOS), `/home/$USER/.local/share/DataGuardianDesktop/ipc/dg-core.sock` (Linux).
  - Windows named pipe `\\.\pipe\data_guardian_core`.
- [ ] Document the IPC binding in `desktop_app/tauri/README.md` (to create) and emphasise local-only communication.
- [ ] If HTTP/gRPC is retained for compatibility, bind strictly to `127.0.0.1` and document firewall considerations in `docs/ipc.md` (to create).
- [ ] Ensure `scripts/build_dg_core.mjs` copies Python packages into `desktop_app/tauri/resources/dg_runtime/` and that the launcher scripts continue to call `python -m dg_core.cli.main`.

## Configuration Updates
- [ ] Update `desktop_app/tauri/tauri.conf.json`:
  - Remove `devUrl`; use `"devUrl": null` and rely on the built assets served via Tauri.
  - Point `frontendDist` to `../ui/dist`.
  - Set `beforeBuildCommand` to `npm --prefix ../ui run build`.
  - Replace `beforeDevCommand` with `npm --prefix ../ui run tauri:dev` that runs Vite in Tauri dev mode without exposing a network port.
  - Add `bundle > resources` entries pointing at `../tauri/resources/**` for packaged Python runtime.
- [ ] Update `desktop_app/ui/package.json` scripts:
  - `"build": "vite build"`
  - `"tauri:dev": "tauri dev --config ../tauri/tauri.conf.json"`
  - Remove any `preview`/`serve` commands that start a standalone web server.
- [ ] Add `desktop_app/ui/vite.config.ts` configuration for `base: "./"` to prevent absolute asset paths when bundled offline.
- [ ] Update `desktop_app/tauri/Cargo.toml` dependencies if needed to drop unused HTTP/gRPC crates and ensure only local IPC transports remain.

## Tests & Quality Gates
- [ ] Replace browser-based Playwright tests with desktop smoke tests using `@tauri-apps/cli`’s testing harness or `spectron`-style e2e. Place them under `tests/desktop/`.
- [ ] Add Python unit tests to guarantee DG Core functionality remains unchanged (`pytest` under `dg_core/tests` and `data_guardian/tests`).
- [ ] Add Rust unit/integration tests under `desktop_app/tauri/tests/` that validate IPC handshake.

## Build & Release Pipeline
- [ ] Create GitHub Actions workflows under `.github/workflows/desktop.yml`:
  - Matrix build for `windows-latest`, `macos-13`, `ubuntu-latest`.
  - Steps: install Rust toolchain, install Node.js + pnpm/npm, set up Python (for DG Core packaging), run tests, run `npm --prefix desktop_app/ui run build`, run `cargo tauri build`.
- [ ] Cache Python wheels and npm dependencies for faster builds.
- [ ] Upload platform-specific installers (`.msi`, `.dmg`, `.AppImage`, `.deb`) as workflow artefacts.

## Code Signing & Auto-Update Placeholders
- [ ] Add placeholder documentation files:
  - `packaging/windows/SIGNING.md` describing how to apply EV Code Signing cert with `signtool.exe`.
  - `packaging/macos/SIGNING.md` covering Apple Developer ID application signing and notarization commands.
  - `packaging/linux/SIGNING.md` covering `.deb` and `.AppImage` signing (GPG + AppImageSignTool).
- [ ] In `desktop_app/tauri/tauri.conf.json`, leave `bundle > windows > signingCertificate` and `bundle > macOS > signingIdentity` fields as placeholders referencing the docs.
- [ ] Enable the Tauri updater plugin once a signing infrastructure exists; stub configuration in `desktop_app/tauri/src/main.rs` to call `tauri::updater::builder()` but guard behind a feature flag `auto-update` until ready.
- [ ] Document update server expectations in `packaging/README.md` (to create).

## Documentation Updates
- [ ] Update `README.md` to describe the desktop installation process and remove instructions about a web terminal.
- [ ] Add `docs/desktop_release_checklist.md` summarising signing, packaging, and verification steps.
- [ ] Update `docs/ipc.md` (new) with socket locations, firewall notes, and troubleshooting tips.

## Validation & Release
- [ ] Perform manual QA on each platform: install, launch, run DG scan/redaction workflow, confirm IPC stability when offline.
- [ ] Verify uninstall routines remove installed binaries but leave user data unless explicitly cleared.
- [ ] Capture screenshots and update marketing collateral if needed.
- [ ] Tag the release (e.g., `vNext-desktop`) once installers are validated and signatures applied.
