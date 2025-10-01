import { useCallback, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api";
import { CommandPalette, CommandDescriptor } from "./components/CommandPalette";
import { TerminalPanel } from "./components/TerminalPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { useKeyboardShortcut } from "./hooks/useKeyboardShortcut";

type View = "terminal" | "settings";

type Settings = {
  socketPath: string;
  logLevel: "info" | "debug" | "warn" | "error";
};

const DEFAULT_SETTINGS: Settings = {
  socketPath: "",
  logLevel: "info",
};

export default function App() {
  const [view, setView] = useState<View>("terminal");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);

  const commands: CommandDescriptor[] = useMemo(
    () => [
      { id: "scan-folder", label: "Scan folder", action: "scan_folder" },
      { id: "redact-file", label: "Redact file", action: "redact_file" },
      { id: "load-policy", label: "Load policy", action: "load_policy" },
      { id: "run-policy-test", label: "Run policy test", action: "run_policy_test" },
      { id: "ping", label: "Ping core", action: "ping" },
    ],
    []
  );

  useKeyboardShortcut(["Meta+K", "Control+K"], () => setPaletteOpen(true));
  useKeyboardShortcut(["Escape"], () => setPaletteOpen(false));

  const handleSettingsUpdate = useCallback((newSettings: Settings) => {
    setSettings(newSettings);
    void invoke("init_core", { config: newSettings });
  }, []);

  const requestPing = async () => {
    await invoke("send_request", { payload: { action: "ping" } });
  };

  return (
    <div className="flex h-screen w-screen flex-col bg-surface text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div>
          <h1 className="text-xl font-semibold">Data Guardian</h1>
          <p className="text-sm text-slate-400">Tauri desktop companion for DG Core.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={requestPing}
            className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-accent hover:text-accent"
          >
            Send Ping
          </button>
          <button
            onClick={() => setPaletteOpen(true)}
            className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-slate-950 shadow transition hover:brightness-110"
          >
            Command Palette
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <nav className="flex w-48 flex-col border-r border-slate-800 bg-slate-950/40 p-4">
          <button
            onClick={() => setView("terminal")}
            className={`rounded-lg px-3 py-2 text-left text-sm font-medium transition ${
              view === "terminal" ? "bg-accent/20 text-accent" : "text-slate-300 hover:bg-slate-800"
            }`}
          >
            Terminal
          </button>
          <button
            onClick={() => setView("settings")}
            className={`mt-2 rounded-lg px-3 py-2 text-left text-sm font-medium transition ${
              view === "settings" ? "bg-accent/20 text-accent" : "text-slate-300 hover:bg-slate-800"
            }`}
          >
            Settings
          </button>
        </nav>

        <main className="flex-1 overflow-auto p-6">
          {view === "terminal" ? <TerminalPanel /> : <SettingsPanel onInit={handleSettingsUpdate} />}
        </main>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} commands={commands} />
    </div>
  );
}
