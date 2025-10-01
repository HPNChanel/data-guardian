# Desktop IPC Reference

Data Guardian Desktop keeps all shell-to-core communication on the local machine.

## Socket locations

| Platform | Transport | Location |
| --- | --- | --- |
| macOS | Unix domain socket | `~/Library/Application Support/DataGuardianDesktop/ipc/dg-core.sock` |
| Linux | Unix domain socket | `/home/$USER/.local/share/DataGuardianDesktop/ipc/dg-core.sock` |
| Windows | Named pipe | `\\.\pipe\data_guardian_core` |

The Unix sockets are created inside the user-specific application data directory. Stale sockets are removed on launch. Ensure the parent `ipc/` directory is writable by the current user.

## Firewall guidance

The desktop build disables TCP endpoints by default. The optional TCP JSON-RPC listener is compiled only when the `debug-tcp-fallback` Cargo feature is enabled. If you temporarily expose the TCP interface for debugging, bind it to `127.0.0.1` and allow the process through your local firewall. Never expose the port to untrusted networks.

## Troubleshooting

- **Socket already in use** – Remove the `dg-core.sock` file and relaunch the desktop app.
- **Permission denied** – Verify the runtime directory under the user's application data folder has the correct owner and permissions.
- **Antivirus interference** – On Windows, allow the named pipe `\\.\pipe\data_guardian_core` through any endpoint security tooling.
- **Transport mismatch** – Confirm the Tauri settings point to the desired transport and that `debug-tcp-fallback` is disabled for production builds.
