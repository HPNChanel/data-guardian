import { useEffect, useRef, useState } from "react";

import DgPanel, { type DgPanelHandle } from "./components/DgPanel";
import SettingsPanel from "./components/SettingsPanel";
import Terminal, { type TerminalHandle } from "./components/Terminal";
import { useSettingsStore } from "./state/settings";

const App = () => {
  const terminalRef = useRef<TerminalHandle>(null);
  const panelRef = useRef<DgPanelHandle>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { load, status } = useSettingsStore((state) => ({
    load: state.load,
    status: state.status,
  }));

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey)) {
        return;
      }
      const key = event.key.toLowerCase();
      if (key === "k") {
        event.preventDefault();
        terminalRef.current?.clear();
      }
      if (key === "f") {
        event.preventDefault();
        const buffer = terminalRef.current?.getBuffer();
        if (buffer) {
          panelRef.current?.scanText(buffer);
        }
      }
      if (key === "r") {
        event.preventDefault();
        const selection = terminalRef.current?.getSelection() || terminalRef.current?.getBuffer();
        if (selection) {
          panelRef.current?.redactText(selection);
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-brand">
          <span className="app-title">Data Guardian Desktop</span>
          <span className="app-subtitle">Secure scanning &amp; redaction</span>
        </div>
        <div className="app-actions">
          <span className={`status-pill status-${status}`}>
            {status === "saving" ? "Saving…" : status === "loading" ? "Syncing…" : "Ready"}
          </span>
          <button type="button" onClick={() => setSettingsOpen(true)}>
            Settings
          </button>
        </div>
      </header>
      <main className="app-content">
        <section className="app-terminal">
          <Terminal
            ref={terminalRef}
            onScanBuffer={(buffer) => panelRef.current?.scanText(buffer)}
          />
        </section>
        <aside className="app-panel">
          <DgPanel ref={panelRef} />
        </aside>
      </main>
      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
};

export default App;
