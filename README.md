# Data Guardian

Data Guardian is a hybrid crypto toolkit: AES-GCM or ChaCha20-Poly1305 for content, with RSA-OAEP or X25519 KEM for key wrapping, and Ed25519 for signatures. It provides a Typer-based CLI and an optional FastAPI service.

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

API Server (optional)

- Run: `uvicorn data_guardian.api.main:app --reload`
- Auth: Bearer JWT (HS256). Set `DG_JWT_SECRET` for local testing.
- Endpoints: `POST /encrypt`, `POST /decrypt` using multipart uploads.

Development

- Health checks: `data-guardian selftest` and `data-guardian doctor`.

Testing

- Minimal placeholder tests under `data_guardian/tests/`. Run with `pytest -q` if installed.

License

- MIT
