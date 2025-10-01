# Data Guardian

Data Guardian is a hybrid crypto toolkit: AES-GCM or ChaCha20-Poly1305 for content, with RSA-OAEP or X25519 KEM for key wrapping, and Ed25519 for signatures. It provides a Typer-based CLI, an optional FastAPI service, and a Tauri-based desktop shell that embeds DG Core locally.

Supported Python: 3.10+

Quick Start

- Create venv: `python -m venv venv` and activate (`venv\Scripts\Activate.ps1` on Windows).
- Install deps: `pip install -r data_guardian/requirements.txt`.
- Optional console script: `pip install -e data_guardian` to enable `data-guardian` command.
- Help: `data-guardian --help` or `python -m data_guardian.cli --help`.

CLI Highlights

- List keys: `data-guardian list-keys`
- Generate keys: `data-guardian keygen-rsa|keygen-ed25519|keygen-x25519 --label "name"`
- Encrypt: `data-guardian encrypt -i file -o file.dgd --kid rsa_...`
- Decrypt: `data-guardian decrypt -i file.dgd -o file.out`
- Sign/Verify: `data-guardian sign -i file --kid ed_...` and `data-guardian verify -i file -s file.sig`
- Hash: `data-guardian sha256 -i file`
- Stream modes: `encrypt-stream` / `decrypt-stream`

Recipients and Policy

- Pass `--kid group:ENG` or `--kid role:admin`; the CLI expands them using `data_guardian/policy/recipients.py` and an optional policy file at `<store>/meta/recipients.json`.

Keystore Layout

- Default store under `data_guardian/dg_store/` (configurable). Files: `keys.json`, `keys/<kid>_pub.pem`, and encrypted `keys/<kid>_priv.enc`.

Desktop App

- Build UI: `npm --prefix desktop_app/ui install` then `npm --prefix desktop_app/ui run build`.
- Package Python runtime: `node scripts/build_dg_core.mjs`.
- Launch shell: `cargo tauri dev --manifest-path desktop_app/tauri/src-tauri/Cargo.toml`.
- IPC is restricted to Unix sockets (macOS/Linux) or a Windows named pipe. See `docs/ipc.md` for full details.

Development

- Health checks: `data-guardian selftest` and `data-guardian doctor`.

Testing

- Python: `pytest dg_core/tests data_guardian/tests`.
- Rust: `cargo test --manifest-path desktop_app/tauri/src-tauri/Cargo.toml`.
- Desktop smoke: `node --test tests/desktop/smoke.test.mjs`.

License

- MIT
