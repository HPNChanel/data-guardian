# Install Data Guardian on macOS

This guide walks through installing the tooling required to build and run the Data Guardian desktop
app on macOS. The commands were validated on macOS 13 Ventura but also apply to newer releases.

![Data Guardian desktop overview](images/overview-placeholder.svg)

## Prerequisites
- macOS 13 or later with administrator privileges
- At least 5 GB of free disk space
- Xcode Command Line Tools (`xcode-select --install`)
- Homebrew (https://brew.sh)

## 1. Install language toolchains
```bash
# Install Rust and cargo
brew install rustup-init
rustup-init -y
source "$HOME/.cargo/env"

# Install Node.js 18 LTS and PNPM (optional for faster installs)
brew install node@18 pnpm

# Install Python 3.11 for packaging the embedded runtime
brew install python@3.11
python3.11 -m ensurepip --upgrade
```

## 2. Clone the repository
```bash
mkdir -p ~/code
cd ~/code
git clone https://github.com/<your-org>/data-guardian.git
cd data-guardian
```

## 3. Prepare the Python environment
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r data_guardian/requirements.txt
deactivate
```

The virtual environment is only required when you run Python unit tests locally. The packaged
runtime that ships with desktop builds is generated via the build script.

## 4. Install JavaScript dependencies
```bash
npm --prefix desktop_app/ui install
```

The Tauri CLI is included in the renderer workspace, so there is no need to install it globally.

## 5. Run the desktop shell
```bash
npm --prefix desktop_app/ui run tauri:dev
```

The command builds the React renderer, packages the Python core into the Tauri resources directory,
and launches the desktop window. The application binds to a Unix domain socket under
`~/Library/Application Support/Data Guardian/ipc.sock`.

## 6. Build a signed installer (optional)
If you need a `.dmg` installer for distribution:
```bash
npm --prefix desktop_app/ui run build
node scripts/build_dg_core.mjs
cargo tauri build --manifest-path desktop_app/tauri/src-tauri/Cargo.toml
```
Follow the [release checklist](release.md) for signing and notarisation requirements.

## Next steps
- Review the [user guide](user_guide.md) for workflow tips.
- Consult the [troubleshooting guide](troubleshooting.md) if the socket is missing or permissions are
denying access.
- Ready to contribute? See [contributing guidelines](contributing.md).
