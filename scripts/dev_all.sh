#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="$ROOT_DIR/desktop_app/ui"
TAURI_DIR="$ROOT_DIR/desktop_app/tauri/src-tauri"
PREVIEW_DIR="$ROOT_DIR/dist/release/preview"
BUNDLE_DIR="$TAURI_DIR/target/release/bundle"

log() {
  printf '\033[1;34m[dev-all]\033[0m %s\n' "$1"
}

section() {
  printf '\n\033[1;32m==> %s\033[0m\n' "$1"
}

section "Preparing workspace"
mkdir -p "$ROOT_DIR/dist/release"
rm -rf "$PREVIEW_DIR"
mkdir -p "$PREVIEW_DIR"

section "Installing desktop UI dependencies"
log "npm ci (desktop_app/ui)"
npm --prefix "$UI_DIR" ci

section "Building desktop UI"
log "npm run build"
npm --prefix "$UI_DIR" run build

section "Building Python runtime bundle"
log "node scripts/build_dg_core.mjs"
( cd "$ROOT_DIR" && node scripts/build_dg_core.mjs )

section "Building Tauri application"
log "npx tauri build"
( cd "$TAURI_DIR" && CI=true npx tauri build --ci --config tauri.conf.json )

if [ ! -d "$BUNDLE_DIR" ]; then
  echo "error: expected bundle directory not found at $BUNDLE_DIR" >&2
  exit 1
fi

section "Collecting installers"
if compgen -G "$BUNDLE_DIR/*" > /dev/null; then
  cp -a "$BUNDLE_DIR/." "$PREVIEW_DIR/"
else
  echo "warning: no artefacts found under $BUNDLE_DIR" >&2
fi

section "Running desktop smoke test"
log "node --test tests/desktop/smoke.test.mjs"
( cd "$ROOT_DIR" && node --test tests/desktop/smoke.test.mjs )

section "Success"
log "Preview installers available in: $PREVIEW_DIR"
log "Artefacts:"
find "$PREVIEW_DIR" -maxdepth 2 -type f | sed "s|$ROOT_DIR/||"

cat <<SUMMARY

Next steps:
  - Sign platform-specific installers as required.
  - Validate installers on clean virtual machines.
  - Promote artefacts from $PREVIEW_DIR after validation.
SUMMARY
