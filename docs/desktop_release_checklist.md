# Desktop Release Checklist

1. **Build prerequisites**
   - Update DG Core dependencies and run `pytest` for both `dg_core` and `data_guardian` packages.
   - Build the UI with `npm --prefix desktop_app/ui run build` and run linting/unit tests.
   - Package the embedded runtime with `node scripts/build_dg_core.mjs`.
   - Build the standalone DG Core bundle with `python scripts/build_core_bundle.py` and stash artefacts from `dist/core/`.
   - Record the bundled binary size and cold-start latency so we can catch regressions when dependencies change.
2. **Security & signing**
   - Follow the platform-specific signing guides:
     - Windows EV certificate – see `packaging/windows/SIGNING.md`.
     - macOS Developer ID & notarization – see `packaging/macos/SIGNING.md`.
     - Linux signing for `.deb` and `.AppImage` – see `packaging/linux/SIGNING.md`.
   - Verify signature trust on clean virtual machines.
3. **Installer validation**
   - Install on Windows, macOS, and Linux.
   - Launch the desktop app offline and confirm the IPC socket/pipe handshake succeeds.
   - Run the DG scan and redact workflows end-to-end.
   - Uninstall the application and confirm user data remains intact.
4. **Artefacts & updates**
   - Upload the signed installers to the release page.
   - Ensure the update server metadata matches the published versions (see `packaging/README.md`).
   - Tag the release (e.g., `vNext-desktop`) once QA signs off.
5. **Collateral**
   - Capture fresh screenshots for marketing materials.
   - Update documentation with any new features or configuration flags.
