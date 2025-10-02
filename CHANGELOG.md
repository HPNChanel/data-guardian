# Changelog

## Unreleased

### Breaking Changes
- Removed all web-hosted terminal assets (`index.html`, legacy `src/` bundle, and associated Playwright artefacts). Desktop users must launch the Tauri application under `desktop_app/`.

### Added
- Added `repo_consistency_check.py` and wired it into CI to guard against reintroducing web-terminal artefacts.

### Changed
- Updated desktop documentation to reflect the desktop-only workflow and security posture.
- Cleaned migration notes to document the completed removal of the web terminal.
