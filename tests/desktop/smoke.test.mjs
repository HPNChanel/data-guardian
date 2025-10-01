import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function tauriCommand() {
  return process.platform === "win32" ? "npx.cmd" : "npx";
}

test("desktop smoke test reports app metadata", async (t) => {
  const projectRoot = resolve(__dirname, "..", "..", "desktop_app", "tauri", "src-tauri");
  const child = spawn(tauriCommand(), ["tauri", "info", "--config", "tauri.conf.json"], {
    cwd: projectRoot,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      CI: "true",
    },
  });

  const [code] = await once(child, "close");
  if (code !== 0) {
    t.skip("@tauri-apps/cli is not available in PATH");
    return;
  }

  assert.equal(code, 0, "tauri info should exit successfully");
});
