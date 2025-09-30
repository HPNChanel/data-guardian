import { useEffect, useMemo, useState } from "react";

import { checkUpdates, type ThemePreference, type TransportKind, type UserSettings } from "../api";
import { useSettingsStore } from "../state/settings";

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

const transportOptions: Array<{ value: TransportKind; label: string; hint: string }> = [
  { value: "auto", label: "Auto", hint: "Choose the best transport for this platform." },
  { value: "unix", label: "Unix socket", hint: "Use a Unix domain socket path." },
  { value: "namedpipe", label: "Named pipe", hint: "Windows named pipe path (e.g. \\ \\.\\pipe\\dg-core)." },
  { value: "tcp", label: "TCP", hint: "Connect over localhost TCP." },
];

const themeOptions: Array<{ value: ThemePreference; label: string }> = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const SettingsPanel = ({ open, onClose }: SettingsPanelProps) => {
  const { settings, status, save, applyTheme } = useSettingsStore((state) => ({
    settings: state.settings,
    status: state.status,
    save: state.save,
    applyTheme: state.applyTheme,
  }));
  const [draft, setDraft] = useState<UserSettings>(settings);
  const [updatesMessage, setUpdatesMessage] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (open) {
      setDraft(settings);
      setError("");
      setUpdatesMessage("");
    }
  }, [open, settings]);

  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const endpointLabel = useMemo(() => {
    switch (draft.transport) {
      case "unix":
        return "Socket path";
      case "namedpipe":
        return "Pipe name";
      case "tcp":
        return "Host:port";
      default:
        return "Endpoint";
    }
  }, [draft.transport]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await save(draft);
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleThemeChange = (theme: ThemePreference) => {
    setDraft((prev) => ({ ...prev, theme }));
    applyTheme(theme);
  };

  const disabled = status === "saving";

  return (
    <div className={`settings-overlay ${open ? "open" : ""}`} aria-hidden={!open}>
      <div className="settings-panel" role="dialog" aria-modal="true">
        <header className="settings-header">
          <h2>Settings</h2>
          <button type="button" onClick={onClose} aria-label="Close settings">
            ×
          </button>
        </header>
        <form className="settings-body" onSubmit={handleSubmit}>
          <section>
            <h3>Transport</h3>
            <div className="settings-grid">
              {transportOptions.map((option) => (
                <label key={option.value} className={`settings-card ${draft.transport === option.value ? "selected" : ""}`}>
                  <input
                    type="radio"
                    name="transport"
                    value={option.value}
                    checked={draft.transport === option.value}
                    onChange={() => setDraft((prev) => ({ ...prev, transport: option.value }))}
                  />
                  <span className="settings-card__label">{option.label}</span>
                  <span className="settings-card__hint">{option.hint}</span>
                </label>
              ))}
            </div>
          </section>

          {draft.transport !== "auto" && (
            <section>
              <h3>{endpointLabel}</h3>
              <input
                type="text"
                value={draft.endpoint ?? ""}
                onChange={(event) =>
                  setDraft((prev) => ({ ...prev, endpoint: event.target.value.trim() || null }))
                }
                placeholder={draft.transport === "tcp" ? "127.0.0.1:7878" : ""}
                className="settings-input"
              />
            </section>
          )}

          <section className="settings-row">
            <label className="settings-toggle">
              <input
                type="checkbox"
                checked={draft.allow_network}
                onChange={(event) =>
                  setDraft((prev) => ({ ...prev, allow_network: event.target.checked }))
                }
              />
              <span>
                Allow network access
                <small>Enables DG Core policy calls that require outbound access.</small>
              </span>
            </label>
          </section>

          <section>
            <h3>Theme</h3>
            <div className="settings-options">
              {themeOptions.map((option) => (
                <label key={option.value} className={draft.theme === option.value ? "selected" : ""}>
                  <input
                    type="radio"
                    value={option.value}
                    checked={draft.theme === option.value}
                    onChange={() => handleThemeChange(option.value)}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </section>

          <section className="settings-footer">
            <div className="settings-updates">
              <button
                type="button"
                onClick={async () => {
                  try {
                    const message = await checkUpdates();
                    setUpdatesMessage(message);
                  } catch (err) {
                    setUpdatesMessage((err as Error).message);
                  }
                }}
                disabled={disabled}
              >
                Check for updates
              </button>
              {updatesMessage && <span className="settings-note">{updatesMessage}</span>}
            </div>
            <div className="settings-actions">
              {error && <span className="settings-error">{error}</span>}
              <button type="button" onClick={onClose} disabled={disabled}>
                Cancel
              </button>
              <button type="submit" disabled={disabled}>
                {status === "saving" ? "Saving…" : "Save"}
              </button>
            </div>
          </section>
        </form>
      </div>
    </div>
  );
};

export default SettingsPanel;
