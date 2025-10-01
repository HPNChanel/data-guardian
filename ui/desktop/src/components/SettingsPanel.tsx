import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api";

type Settings = {
  socketPath: string;
  logLevel: "info" | "debug" | "warn" | "error";
};

type SettingsPanelProps = {
  onInit: (settings: Settings) => void;
};

const STORAGE_KEY = "dg-desktop-settings";

export function SettingsPanel({ onInit }: SettingsPanelProps) {
  const [settings, setSettings] = useState<Settings>({
    socketPath: "",
    logLevel: "info",
  });
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as Settings;
        setSettings(parsed);
        onInit(parsed);
      } catch (error) {
        console.error("Failed to parse settings", error);
      }
    }
  }, [onInit]);

  const updateSettings = (partial: Partial<Settings>) => {
    setSettings((previous) => ({ ...previous, ...partial }));
  };

  const saveSettings = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    onInit(settings);
    setStatus("Settings saved and bridge initialized.");
    setTimeout(() => setStatus(null), 2000);
  };

  const handleInitCore = async () => {
    await invoke("init_core", { config: settings });
    setStatus("Core initialization requested.");
    setTimeout(() => setStatus(null), 2000);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-100">Connectivity</h2>
        <p className="mt-1 text-sm text-slate-400">
          Configure the socket path or named pipe used to communicate with the Data Guardian core.
        </p>
        <label className="mt-4 block text-sm font-medium text-slate-300">
          Socket / Pipe Path
          <input
            value={settings.socketPath}
            onChange={(event) => updateSettings({ socketPath: event.target.value })}
            placeholder="/tmp/dg-core.sock"
            className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-accent focus:outline-none"
          />
        </label>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-slate-100">Logs</h2>
        <label className="mt-2 block text-sm font-medium text-slate-300">
          Log Level
          <select
            value={settings.logLevel}
            onChange={(event) => updateSettings({ logLevel: event.target.value as Settings["logLevel"] })}
            className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-accent focus:outline-none"
          >
            <option value="debug">Debug</option>
            <option value="info">Info</option>
            <option value="warn">Warn</option>
            <option value="error">Error</option>
          </select>
        </label>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          onClick={saveSettings}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-slate-950 transition hover:brightness-105"
        >
          Save Settings
        </button>
        <button
          onClick={handleInitCore}
          className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800"
        >
          Initialize Core
        </button>
      </div>

      {status && <div className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-300">{status}</div>}
    </div>
  );
}
