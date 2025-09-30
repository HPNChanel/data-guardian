import { create } from "zustand";

import type { ThemePreference, UserSettings } from "../api";
import { loadSettings as loadSettingsApi, saveSettings as saveSettingsApi } from "../api";

const DEFAULT_SETTINGS: UserSettings = {
  transport: "auto",
  endpoint: null,
  theme: "system",
  allow_network: false,
};

type Status = "idle" | "loading" | "saving" | "error";

interface SettingsState {
  settings: UserSettings;
  status: Status;
  error?: string;
  load: () => Promise<void>;
  save: (settings: UserSettings) => Promise<void>;
  applyTheme: (theme?: ThemePreference) => void;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: DEFAULT_SETTINGS,
  status: "idle",
  async load() {
    set({ status: "loading", error: undefined });
    try {
      const incoming = await loadSettingsApi();
      const merged = { ...DEFAULT_SETTINGS, ...incoming };
      set({ settings: merged, status: "idle" });
      get().applyTheme(merged.theme);
    } catch (error) {
      set({ status: "error", error: (error as Error).message });
    }
  },
  async save(settings) {
    set({ status: "saving", error: undefined, settings });
    try {
      await saveSettingsApi(settings);
      set({ status: "idle", settings });
      get().applyTheme(settings.theme);
    } catch (error) {
      set({ status: "error", error: (error as Error).message });
      throw error;
    }
  },
  applyTheme(theme) {
    const target = theme ?? get().settings.theme ?? "system";
    const root = document.documentElement;
    root.dataset.theme = target;
  },
}));
