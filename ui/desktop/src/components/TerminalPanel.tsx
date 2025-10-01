import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api";

type TerminalPanelProps = {
  onReady?: () => void;
};

export function TerminalPanel({ onReady }: TerminalPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const termRef = useRef<Terminal>();
  const fitAddonRef = useRef<FitAddon>();

  useEffect(() => {
    const terminal = new Terminal({
      fontFamily: "JetBrains Mono, monospace",
      theme: {
        background: "#0f172a",
        foreground: "#e2e8f0",
        cursor: "#38bdf8",
      },
      convertEol: true,
      disableStdin: true,
    });
    const fit = new FitAddon();
    termRef.current = terminal;
    fitAddonRef.current = fit;

    if (containerRef.current) {
      terminal.loadAddon(fit);
      terminal.open(containerRef.current);
      fit.fit();
    }

    const resizeObserver = new ResizeObserver(() => fit.fit());
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    let unlisten: (() => void) | null = null;
    (async () => {
      await invoke("subscribe_logs");
      unlisten = await listen<string>("core://log", (event) => {
        terminal.writeln(event.payload);
      });
      onReady?.();
    })();

    return () => {
      unlisten?.();
      resizeObserver.disconnect();
      terminal.dispose();
    };
  }, [onReady]);

  return <div ref={containerRef} className="h-full w-full overflow-hidden rounded-lg border border-slate-700 bg-slate-950" />;
}
