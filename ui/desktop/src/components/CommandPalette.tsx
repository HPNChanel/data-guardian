import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api";

export type CommandDescriptor = {
  id: string;
  label: string;
  action: string;
  payload?: Record<string, unknown>;
};

type CommandPaletteProps = {
  open: boolean;
  onClose: () => void;
  commands: CommandDescriptor[];
};

export function CommandPalette({ open, onClose, commands }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const filtered = useMemo(() => {
    if (!query) return commands;
    return commands.filter((command) => command.label.toLowerCase().includes(query.toLowerCase()));
  }, [commands, query]);

  useEffect(() => {
    if (!open) {
      setQuery("");
    }
  }, [open]);

  const onExecute = async (command: CommandDescriptor) => {
    setBusy(true);
    try {
      await invoke("send_request", {
        payload: {
          action: command.action,
          ...command.payload,
        },
      });
    } finally {
      setBusy(false);
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-8">
      <div className="w-full max-w-xl rounded-2xl border border-slate-700 bg-slate-900/90 p-6 shadow-2xl backdrop-blur">
        <div className="flex items-center gap-3">
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search commands..."
            className="w-full rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-2 text-slate-100 outline-none focus:border-accent"
          />
          <button
            onClick={onClose}
            className="rounded-lg border border-transparent px-3 py-2 text-sm font-medium text-slate-300 hover:border-slate-600 hover:bg-slate-800"
          >
            Esc
          </button>
        </div>
        <div className="mt-4 max-h-60 space-y-2 overflow-y-auto">
          {filtered.length === 0 && <p className="text-sm text-slate-400">No commands match that search.</p>}
          {filtered.map((command) => (
            <button
              key={command.id}
              disabled={busy}
              onClick={() => onExecute(command)}
              className="flex w-full items-center justify-between rounded-lg border border-slate-800 bg-slate-800/40 px-4 py-3 text-left text-sm font-medium text-slate-100 transition hover:border-accent hover:bg-slate-800 focus:outline-none"
            >
              <span>{command.label}</span>
              <span className="text-xs text-slate-500">Enter</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
