# Migration Plan: Desktop-Only Data Guardian

> Status: completed. The web-hosted terminal has been removed and the repository now aligns with the desktop-only architecture described below.

## Repository map
- The repository now ships with the following high-level layout:
  ```text
  .
  ├── README.md
  ├── README_desktop.md
  ├── CHANGELOG.md
  ├── data_guardian/
  ├── dg_core/
  ├── desktop_app/
  │   ├── tauri/
  │   │   ├── src-tauri/
  │   │   └── tests/
  │   └── ui/
  │       ├── public/
  │       └── src/
  ├── packaging/
  ├── scripts/
  └── tests/
      └── desktop/
  ```

## Identify & Remove Web-Hosted Terminal Assets
- Legacy artefacts (`index.html`, `src/`, `tests/ui/`, and `test-results/`) have been removed.
- `repo_consistency_check.py` enforces their absence in CI to prevent regressions.
- Documentation has been scrubbed of browser-hosted terminal references.

## Desktop Application Restructure
- The Tauri workspace lives under `desktop_app/tauri/` and targets the renderer bundled from `desktop_app/ui/`.
- IPC is driven exclusively through Tauri commands; no HTTP bridge remains.
- Future UI features should be added under `desktop_app/ui/src/` and consume the local-only APIs exposed by the Rust host.

### Updated directory tree (target)
- The target layout above matches the current repository state. New platform-specific assets should continue to follow this structure.

## IPC & Runtime Strategy
- [ ] Update `desktop_app/tauri/src/process/mod.rs` to eliminate TCP fallback by default (keep the code path guarded behind a feature flag for debugging only). Prefer:
  - Unix domain sockets at `~/Library/Application Support/Data Guardian/ipc/dg-core.sock` (macOS), `~/.config/data-guardian/ipc/dg-core.sock` (Linux).
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
- `desktop_app/ui/package.json` only exposes build and desktop dev scripts; standalone preview/serve commands have been removed.
- `desktop_app/ui/vite.config.ts` defines `base: "./"` to keep asset paths relative for bundled builds.
- [ ] Update `desktop_app/tauri/Cargo.toml` dependencies if needed to drop unused HTTP/gRPC crates and ensure only local IPC transports remain.

## Tests & Quality Gates
- [ ] Replace browser-based Playwright tests with desktop smoke tests using `@tauri-apps/cli`’s testing harness or `spectron`-style e2e. Place them under `tests/desktop/`.
- [ ] Add Python unit tests to guarantee DG Core functionality remains unchanged (`pytest` under `dg_core/tests` and `data_guardian/tests`).
- Desktop smoke tests and Rust integration tests live under `desktop_app/tauri/tests/` and `tests/desktop/`.
- `repo_consistency_check.py` is executed in CI to guarantee the desktop layout stays intact.

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
- `README.md` now describes the desktop installation process and omits browser-based guidance.
- [ ] Add `docs/desktop_release_checklist.md` summarising signing, packaging, and verification steps.
- [ ] Update `docs/ipc.md` (new) with socket locations, firewall notes, and troubleshooting tips.

## Validation & Release
- [ ] Perform manual QA on each platform: install, launch, run DG scan/redaction workflow, confirm IPC stability when offline.
- [ ] Verify uninstall routines remove installed binaries but leave user data unless explicitly cleared.
- [ ] Capture screenshots and update marketing collateral if needed.
- [ ] Tag the release (e.g., `vNext-desktop`) once installers are validated and signatures applied.
