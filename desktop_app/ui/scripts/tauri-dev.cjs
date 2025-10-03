#!/usr/bin/env node
const path = require('node:path');
const cli = require('@tauri-apps/cli');

const uiDir = path.resolve(__dirname, '..');
const tauriSrcDir = path.resolve(uiDir, '../tauri/src-tauri');
const configPath = path.resolve(tauriSrcDir, 'tauri.conf.json');

process.env.TAURI_APP_PATH = tauriSrcDir;
process.env.TAURI_FRONTEND_PATH = uiDir;

cli
  .run(['dev', '--config', configPath], 'npm run tauri:dev')
  .catch((error) => {
    cli.logError(error.message);
    process.exit(1);
  });
