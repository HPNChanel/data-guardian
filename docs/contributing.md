# Contributing to Data Guardian

Thank you for investing time in Data Guardian. This guide explains how to set up a development
environment, what coding standards we follow, and how we document releases.

## Getting started
1. Fork the repository and clone your fork locally.
2. Install the desktop prerequisites for your OS (see the `docs/install_*.md` guides).
3. Create a feature branch from `main`: `git checkout -b feat/<topic>`.
4. Run the desktop shell with `npm --prefix desktop_app/ui run tauri:dev` to verify your
   environment before making changes.

## Coding style
Apply the following tooling before you open a pull request:

### Python (`data_guardian/`, `dg_core/`)
- Format code with [Black](https://black.readthedocs.io/en/stable/) (`black .`).
- Lint with [Ruff](https://docs.astral.sh/ruff/) (`ruff check .`).
- Prefer type hints on public functions and keep docstrings concise.

### Rust (`desktop_app/tauri/src-tauri/`)
- Run `cargo fmt` to apply rustfmt.
- Run `cargo clippy --all-targets --all-features -- -D warnings`.
- Keep modules small and favour `anyhow::Result` for fallible operations in the Tauri commands.

### TypeScript/React (`desktop_app/ui/`)
- Use `npm run lint` (ESLint) and `npm run format` (Prettier).
- Component files should co-locate styles and tests when practical.
- Prefer hooks over class components.

### Documentation
- Markdown files must wrap at ~100 characters per line for readability.
- Use relative links within the `docs/` directory.
- When adding screenshots, store them under `docs/images/`.

## Commit conventions
We use [Conventional Commits](https://www.conventionalcommits.org/) to keep history structured. Use
one of the following prefixes when possible:
- `feat:` new end-user functionality
- `fix:` bug fixes
- `docs:` documentation-only changes
- `refactor:` internal code changes that do not affect behaviour
- `test:` adding or updating tests
- `chore:` tooling, CI, or dependency updates

Limit each commit to a focused change set and include context in the body when necessary.

## Testing checklist
Before opening a pull request, run the relevant suites:
- `pytest dg_core/tests data_guardian/tests`
- `cargo test --manifest-path desktop_app/tauri/src-tauri/Cargo.toml`
- `npm --prefix desktop_app/ui run test`
- `node --test tests/desktop/smoke.test.mjs`
Include the command output in the pull request description when tests are skipped due to platform
limitations.

## Release tags
Releases follow semantic versioning. Tag the repository with `vMAJOR.MINOR.PATCH` and update the
versions in the desktop, CLI, and core packages before tagging. See `docs/release.md` for the full
checklist and signing requirements.

## Code review expectations
- Keep pull requests under 500 lines of diff when possible.
- Provide a summary of changes, screenshots for UI updates, and a test plan.
- Respond to review comments within two business days.

## Reporting issues
Create a GitHub issue that includes:
- Steps to reproduce
- Expected vs. actual behaviour
- Platform details (OS, Data Guardian version)
- Relevant log snippets (`desktop_app/tauri/src-tauri/target/debug/*.log`)
