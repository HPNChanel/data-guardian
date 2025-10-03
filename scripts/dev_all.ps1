#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"

function Resolve-Root {
    param()
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    $full = Resolve-Path (Join-Path $scriptRoot "..")
    return $full.Path
}

$root = Resolve-Root
$uiDir = Join-Path $root "desktop_app/ui"
$tauriDir = Join-Path $root "desktop_app/tauri/src-tauri"
$bundleDir = Join-Path $tauriDir "target/release/bundle"
$previewDir = Join-Path $root "dist/release/preview"

function Section($message) {
    Write-Host "`n==> $message" -ForegroundColor Green
}

function Log($message) {
    Write-Host "[dev-all] $message" -ForegroundColor Blue
}

Section "Preparing workspace"
New-Item -ItemType Directory -Force -Path (Join-Path $root "dist/release") | Out-Null
if (Test-Path $previewDir) {
    Remove-Item $previewDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $previewDir | Out-Null

Section "Installing desktop UI dependencies"
Log "npm ci (desktop_app/ui)"
npm --prefix $uiDir ci

Section "Building desktop UI"
Log "npm run build"
npm --prefix $uiDir run build

Section "Building Python runtime bundle"
Log "node scripts/build_dg_core.mjs"
Push-Location $root
try {
    node scripts/build_dg_core.mjs
}
finally {
    Pop-Location
}

Section "Building Tauri application"
Log "npx tauri build"
Push-Location $tauriDir
$previousCI = $env:CI
try {
    $env:CI = "true"
    npx tauri build --ci --config tauri.conf.json
}
finally {
    if ($null -eq $previousCI) {
        Remove-Item Env:CI -ErrorAction SilentlyContinue
    } else {
        $env:CI = $previousCI
    }
    Pop-Location
}

if (-not (Test-Path $bundleDir)) {
    throw "Expected bundle directory not found at $bundleDir"
}

Section "Collecting installers"
$items = Get-ChildItem -Path $bundleDir -Force
if ($items) {
    foreach ($item in $items) {
        Copy-Item -Path $item.FullName -Destination $previewDir -Recurse -Force
    }
} else {
    Write-Warning "No artefacts found under $bundleDir"
}

Section "Running desktop smoke test"
Log "node --test tests/desktop/smoke.test.mjs"
Push-Location $root
try {
    node --test tests/desktop/smoke.test.mjs
}
finally {
    Pop-Location
}

Section "Success"
Log "Preview installers available in: $previewDir"
Log "Artefacts:"
Get-ChildItem -Path $previewDir -Recurse -File | ForEach-Object {
    $_.FullName.Substring($root.Length + 1)
}

Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  - Sign platform-specific installers as required."
Write-Host "  - Validate installers on clean virtual machines."
Write-Host "  - Promote artefacts from $previewDir after validation."
