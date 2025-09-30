#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const RESOURCES_DIR = path.join(ROOT, "resources", "dg_runtime");
const BIN_DIR = path.join(RESOURCES_DIR, "bin");
const LIB_DIR = path.join(RESOURCES_DIR, "lib");
const VERSION = process.env.npm_package_version ?? "0.0.0";

const projects = [
  {
    source: path.join(ROOT, "dg_core", "src", "dg_core"),
    target: path.join(LIB_DIR, "dg_core"),
  },
  {
    source: path.join(ROOT, "data_guardian", "src", "data_guardian"),
    target: path.join(LIB_DIR, "data_guardian"),
  },
];

async function ensureCleanDir(dir) {
  await fs.rm(dir, { recursive: true, force: true });
  await fs.mkdir(dir, { recursive: true });
}

async function copyTree(from, to) {
  await fs.mkdir(to, { recursive: true });
  await fs.cp(from, to, { recursive: true });
}

async function writeWrapperScripts() {
  const unixScript = `#!/usr/bin/env python3\nimport runpy\nimport sys\n\nif __name__ == "__main__":\n    runpy.run_module("dg_core.cli.main", run_name="__main__")\n`;
  const windowsScript = `@echo off\r\npython -m dg_core.cli.main %*\r\n`;

  const unixPath = path.join(BIN_DIR, "dg");
  const windowsPath = path.join(BIN_DIR, "dg.cmd");

  await fs.writeFile(unixPath, unixScript, { encoding: "utf8" });
  await fs.writeFile(windowsPath, windowsScript, { encoding: "utf8" });

  try {
    await fs.chmod(unixPath, 0o755);
  } catch (error) {
    console.warn("warning: failed to set executable bit on", unixPath, error.message);
  }
}

async function writeManifest() {
  const manifest = {
    version: VERSION,
    generated_at: new Date().toISOString(),
    contents: projects.map((project) => path.basename(project.target)),
  };
  await fs.writeFile(path.join(RESOURCES_DIR, "manifest.json"), JSON.stringify(manifest, null, 2));
  await fs.writeFile(path.join(RESOURCES_DIR, "VERSION"), `${VERSION}\n`, "utf8");
}

(async () => {
  console.log("[dg-runtime] preparing resources in", RESOURCES_DIR);
  await ensureCleanDir(RESOURCES_DIR);
  await fs.mkdir(BIN_DIR, { recursive: true });
  await fs.mkdir(LIB_DIR, { recursive: true });

  for (const project of projects) {
    try {
      await copyTree(project.source, project.target);
      console.log("[dg-runtime] copied", project.source, "->", project.target);
    } catch (error) {
      console.warn("[dg-runtime] skipping", project.source, error.message);
    }
  }

  await writeWrapperScripts();
  await writeManifest();

  console.log("[dg-runtime] build completed");
})().catch((error) => {
  console.error("[dg-runtime] build failed", error);
  process.exitCode = 1;
});
