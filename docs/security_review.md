# Security Review Checklist

## Local-Only IPC
- [x] TCP transports validate loopback-only bindings.
- [x] Unix socket defaults to a per-user runtime directory under `runtime_config_dir()/ipc`.
- [x] Non-loopback TCP hosts raise configuration errors during validation.

## Filesystem Safeguards
- [x] All JSON-RPC file parameters are normalised and reject `..` traversal sequences.
- [x] Policy file access is restricted to trusted roots (default policies, runtime config, working directory).
- [x] Output locations are resolved before use and directories are created with least privilege.

## Runtime Hygiene
- [x] Unix domain sockets are recreated on startup and cleaned up on shutdown.
- [x] Temporary runtime paths live under the per-user sandbox.

## Offline & Privacy Guarantees
- [x] Configurable policy-only offline mode disables scanning and redaction operations.
- [x] CLI surfaces the offline restriction to avoid surprising failures.
- [x] Crash logs and analytics are confined to local storage; nothing is uploaded automatically.

## Testing & Verification
- [x] Unit tests cover validation helpers for host and path sanitisation.
- [x] Integration tests assert that offline mode blocks stateful operations while health checks remain functional.
