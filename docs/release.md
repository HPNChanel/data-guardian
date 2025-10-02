# Desktop release process

This document captures the end-to-end workflow for shipping a signed desktop release with auto-update support across macOS, Windows, and Linux.

## 1. Prerequisites

1. **Update the release version**
   - Bump versions in the following files:
     - `desktop_app/tauri/src-tauri/tauri.conf.json` (`version`)
     - `desktop_app/ui/package.json` and `package-lock.json`
     - Python packages (`dg_core/pyproject.toml`, `data_guardian/pyproject.toml`)
   - Run `npm install` in `desktop_app/ui` after bumping to keep the lockfile consistent.
2. **Secrets and certificates**
   - Generate a Tauri updater key pair via `cargo tauri signer generate` and store the public key in `desktop_app/tauri/src-tauri/tauri.conf.json`.
   - Upload the private key and password to repository secrets as `TAURI_SIGNING_PRIVATE_KEY` and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`.
   - macOS:
     - Install an **Apple Developer ID Application** certificate locally for manual builds.
     - Store the base64-encoded certificate, password, and `APPLE_TEAM_ID` as GitHub secrets if automated signing is desired.
     - If notarization is required, set `DG_APPLE_NOTARIZE=true`, `APPLE_DEVELOPER_ID`, and `APPLE_DEVELOPER_PASSWORD` secrets; otherwise the workflow will default to ad-hoc signing.
   - Windows:
     - Acquire a code-signing certificate compatible with `signtool.exe` and reference it in `packaging/windows/SIGNING.md`.
     - Provide the certificate path/password as GitHub secrets when ready. The build falls back to unsigned debug installers.
   - Linux: no signing is required for the `.AppImage`, but you may optionally provision GPG keys for `.deb`/`.rpm` repositories.
3. **GitHub Release configuration**
   - The updater expects a `latest.json` asset on each GitHub Release. Ensure the repository tag is created as `vX.Y.Z` to match semantic versioning.

## 2. Local verification

1. Build the Python runtime bundle:
   ```bash
   npm --prefix desktop_app/ui ci
   npm --prefix desktop_app/ui run build
   node scripts/build_dg_core.mjs
   ```
2. Run the full desktop test suite:
   ```bash
   pytest dg_core/tests data_guardian/tests
   cargo test --locked --manifest-path desktop_app/tauri/src-tauri/Cargo.toml
   node --test tests/desktop/smoke.test.mjs
   ```
3. Produce installers locally for smoke tests:
   ```bash
   cargo install tauri-cli --locked
   cargo tauri build --ci --config desktop_app/tauri/src-tauri/tauri.conf.json
   ```
4. Validate the generated installer per platform:
   - **macOS `.dmg`**: install the app, confirm it launches, starts the background daemon, and `scripts/health_check.mjs` (or `curl http://localhost:8787/health`) returns healthy.
   - **Windows `.msi`**: install, ensure the service starts without security prompts, and run `scripts\health_check.ps1`.
   - **Linux `.AppImage`**: mark executable, launch, and run `scripts/health_check.mjs`.

## 3. Creating the release

1. Commit the version bump and tag the release locally:
   ```bash
   git commit -am "release: vX.Y.Z"
   git tag vX.Y.Z
   git push origin main --tags
   ```
2. The [`Desktop Release`](../.github/workflows/release.yml) workflow triggers on the pushed tag. It:
   - Builds the React UI, packages the Python core, and runs tests on macOS, Windows, and Ubuntu runners.
   - Produces `.dmg`, `.msi`/`.exe`, `.AppImage`, and signed update archives (`*.tar.gz` + `latest.json`).
   - Publishes the artifacts to the GitHub Release with SHA256 checksums.
3. Monitor the workflow for signing or notarization warnings. If notarization secrets are missing the job defaults to ad-hoc signing (acceptable for CI validation, but not for production distribution).

## 4. Post-release validation

1. Download each installer from the GitHub Release and perform the smoke tests described above on clean VMs.
2. Verify auto-update by installing the previous version, publishing a new release, and observing the in-app updater prompt. Confirm the `latest.json` asset references the new version and has a valid signature.
3. Archive notarization logs (if applicable) and update `docs/desktop_release_checklist.md` with any deviations or incident notes.

## 5. Troubleshooting

- **Updater signature errors**: confirm `TAURI_SIGNING_PRIVATE_KEY` and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` secrets are present and the public key matches `tauri.conf.json`.
- **macOS Gatekeeper blocks**: ensure the Developer ID certificate is installed and notarization secrets are configured. The workflow exposes `DG_APPLE_NOTARIZE` to toggle notarization.
- **Windows SmartScreen warnings**: once the signing certificate is available, update `packaging/windows/SIGNING.md` with import instructions and configure the workflow secrets to sign with `signtool`.
- **Python runtime missing**: rerun `node scripts/build_dg_core.mjs` and confirm the resulting archive is included under `desktop_app/tauri/src-tauri/target/`. The CI workflow fails if the core bundle is absent.

Following this checklist ensures every tagged release publishes cross-platform installers with the embedded core runtime and a signed auto-update feed.
