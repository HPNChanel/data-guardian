# Troubleshooting Data Guardian Desktop

The issues below cover the most common blockers seen during local development and production builds.
Each section includes detection tips and remediation steps.

## Desktop socket or pipe is missing
**Symptoms**
- The desktop app reports "Unable to reach core" or hangs on the splash screen.
- `npm --prefix desktop_app/ui run tauri:dev` logs `ENOENT` errors for the socket path.
- No file exists at the expected location:
  - macOS: `~/Library/Application Support/Data Guardian/ipc.sock`
  - Linux: `~/.local/share/data-guardian/ipc.sock`
  - Windows: `\\.\pipe\data_guardian_ipc`

**Resolution**
1. Confirm the Python core binary started by checking the terminal for a `Core ready` message.
2. If the process failed to spawn, run `python -m data_guardian.cli selftest` to reveal dependency
   errors.
3. Remove any stale IPC endpoints and restart the shell:
   ```bash
   # macOS
   rm -f "$HOME/Library/Application Support/Data Guardian/ipc.sock"

   # Linux
   rm -f "$HOME/.local/share/data-guardian/ipc.sock"

   npm --prefix desktop_app/ui run tauri:dev
   ```
   ```powershell
   # Windows
   Remove-Item \\?\pipe\data_guardian_ipc -ErrorAction SilentlyContinue
   npm --prefix desktop_app\ui run tauri:dev
   ```
4. On Linux, ensure your user has permission to create files under `~/.local/share`
   (see the next section).

## Permission errors when accessing the key store
**Symptoms**
- The CLI or desktop app shows `Permission denied` when writing to the store directory.
- Logs mention `EACCES` for paths inside `~/.local/share/data-guardian` or
  `~/Library/Application Support/Data Guardian`.

**Resolution**
1. Verify ownership of the directory:
   ```bash
   ls -ld ~/.local/share/data-guardian
   ```
2. Fix the owner and permissions if needed:
   ```bash
   sudo chown -R "$USER":"$USER" ~/.local/share/data-guardian
   chmod -R u+rwX ~/.local/share/data-guardian
   ```
3. On macOS, ensure the app has Full Disk Access if you point it at protected folders (System
   Settings → Privacy & Security → Full Disk Access).
4. When running inside corporate sandboxes, run the desktop shell once with elevated privileges to
   allow the OS to prompt for required permissions.

## Antivirus blocks Windows named pipes
**Symptoms**
- The desktop shell launches but shows `Pipe initialization failed`.
- Antivirus or endpoint protection logs a blocked behaviour targeting `\\.\pipe\data_guardian_ipc`.
- Restarting the app does not recreate the pipe.

**Resolution**
1. Temporarily disable real-time scanning to confirm the AV is the root cause.
2. Add an allowlist rule for the `data-guardian.exe` process and the pipe path.
3. If group policy prevents allowlisting, change the pipe name to one already approved by your
   organisation by setting the `DG_PIPE_NAME` environment variable before launching Tauri:
   ```powershell
   $env:DG_PIPE_NAME = "data_guardian_allowlisted"
   npm --prefix desktop_app\ui run tauri:dev
   ```
4. After adjusting policies, restart the desktop shell so it can recreate the pipe.

## Need more help?
- Run `data-guardian doctor` to generate a support bundle.
- Attach `desktop_app/tauri/src-tauri/target/debug/*.log` files when filing an issue.
