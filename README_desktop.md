# Data Guardian Desktop

This directory contains the Tauri-based desktop companion application for Data Guardian.

## Tech Stack

- [Tauri](https://tauri.app) 1.x for the Rust host shell
- [React](https://react.dev/) + [Vite](https://vitejs.dev/) for the renderer UI
- [xterm.js](https://xtermjs.org/) for the log terminal

All assets are bundled locally; the application does not load remote resources at runtime.

## Prerequisites

- Rust toolchain with `cargo`
- Node.js 18+ with `npm`
- `pnpm` is not required; the project uses npm scripts

## Install Dependencies

```bash
cd ui/desktop
npm install
```

The Tauri CLI is installed locally as a dev dependency. You can run it through the npm scripts defined in `package.json`.

## Development

Run the Vite dev server and Tauri shell together:

```bash
npm run tauri dev
```

The dev profile still serves local assets and keeps external requests disabled by CSP.

## Build

Create a production desktop bundle:

```bash
cargo tauri build
```

This command builds the React frontend, bundles it with the Tauri shell, and produces platform-specific artifacts under `ui/desktop/src-tauri/target/release/bundle/`.

## Application Features

- Embedded xterm.js terminal that streams logs from the Python core bridge
- Command palette (`Ctrl/Cmd + K`) for quickly dispatching DG Core actions
- Settings page for socket/pipe path and log level configuration
- Persistent window state across launches
- Mock Python core daemon that responds to `ping` for local testing

## Mock Core

Until the real Python DG Core is available, the bridge spins up a mock Unix domain socket server. Actions sent via the command palette or the "Send Ping" button will echo back responses in the terminal log stream.

The default socket is `${TMPDIR}/dg-core.sock` on Unix-like systems. Configure an alternate endpoint from the Settings tab.
