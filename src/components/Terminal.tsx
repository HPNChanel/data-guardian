import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import { Command } from "@tauri-apps/plugin-shell";
import { listen } from "@tauri-apps/api/event";
import { homeDir } from "@tauri-apps/api/path";
import { FitAddon } from "xterm-addon-fit";
import { Terminal as XTerm } from "xterm";

import "xterm/css/xterm.css";

interface TerminalProps {
  onScanBuffer?: (buffer: string) => void;
}

export interface TerminalHandle {
  clear: () => void;
  getBuffer: () => string;
  getSelection: () => string;
  focus: () => void;
}

const BUFFER_LIMIT = 2 * 1024 * 1024; // 2MB

class TextRingBuffer {
  private chunks: string[] = [];
  private length = 0;

  constructor(private readonly limit: number) {}

  push(data: string) {
    if (!data) return;
    this.chunks.push(data);
    this.length += data.length;

    while (this.length > this.limit && this.chunks.length > 1) {
      const removed = this.chunks.shift();
      if (removed) {
        this.length -= removed.length;
      }
    }
  }

  value() {
    return this.chunks.join("");
  }

  clear() {
    this.chunks = [];
    this.length = 0;
  }
}

const isWindows = navigator.userAgent.toLowerCase().includes("windows");

async function createSystemShell() {
  const command = await Command.create("system-shell", [], {
    cwd: await homeDir(),
  });
  return command;
}

const Terminal = forwardRef<TerminalHandle, TerminalProps>(({ onScanBuffer }, ref) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const termRef = useRef<XTerm | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const commandRef = useRef<Command | null>(null);
  const bufferRef = useRef(new TextRingBuffer(BUFFER_LIMIT));
  const [status, setStatus] = useState<"connecting" | "ready" | "error">("connecting");
  const [dgMode, setDgMode] = useState(false);
  const dgModeRef = useRef(false);
  const scanCallbackRef = useRef(onScanBuffer);


  useImperativeHandle(ref, () => ({
    clear() {
      termRef.current?.reset();
      bufferRef.current.clear();
    },
    getBuffer() {
      return bufferRef.current.value();
    },
    getSelection() {
      return termRef.current?.getSelection() ?? "";
    },
    focus() {
      termRef.current?.focus();
    },
  }));

  useEffect(() => {
    dgModeRef.current = dgMode;
  }, [dgMode]);

  useEffect(() => {
    scanCallbackRef.current = onScanBuffer;
  }, [onScanBuffer]);

  const appendOutput = useCallback((text: string) => {
    if (!termRef.current) return;
    termRef.current.write(text);
    bufferRef.current.push(text);
  }, []);

  const connectShell = useCallback(async () => {
    setStatus("connecting");
    try {
      const command = await createSystemShell();
      commandRef.current = command;

      command.stdout.on("data", ({ data }) => {
        appendOutput(data);
        if (dgMode && onScanBuffer) {
          onScanBuffer(bufferRef.current.value());
        }
      });

      command.stderr.on("data", ({ data }) => {
        appendOutput(data);
      });

      command.on("close", ({ code, signal }) => {
        appendOutput(`\r\n[process exited: code=${code ?? ""} signal=${signal ?? ""}]\r\n`);
        setStatus("error");
      });

      await command.spawn();
      setStatus("ready");
    } catch (error) {
      appendOutput(`\r\n[shell error] ${(error as Error).message}\r\n`);
      setStatus("error");
    }
  }, [appendOutput, dgMode, onScanBuffer]);

  useEffect(() => {
    const fitAddon = new FitAddon();
    fitAddonRef.current = fitAddon;

    const term = new XTerm({
      allowTransparency: true,
      convertEol: true,
      cursorBlink: true,
      fontFamily: isWindows ? "Consolas, monospace" : "JetBrains Mono, monospace",
      fontSize: 13,
      theme: {
        background: "#020617",
        foreground: "#e2e8f0",
        cursor: "#38bdf8",
        selection: "rgba(56, 189, 248, 0.35)",
      },
    });

    termRef.current = term;
    term.loadAddon(fitAddon);

    if (containerRef.current) {
      term.open(containerRef.current);
      fitAddon.fit();
    }

    const onResize = () => {
      try {
        fitAddon.fit();
      } catch {
        /* ignore */
      }
    };

    const resizeObserver = new ResizeObserver(onResize);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    term.onData((data) => {
      if (commandRef.current) {
        commandRef.current.write(data);
      }
    });

    connectShell();

    return () => {
      resizeObserver.disconnect();
      commandRef.current?.kill();
      term.dispose();
      termRef.current = null;
    };
  }, [connectShell]);

  useEffect(() => {
    const unlisten = listen<string>("dg-core:error", (event) => {
      appendOutput(`\r\n[DG Core] ${event.payload}\r\n`);
    });
    return () => {
      unlisten.then((dispose) => dispose());
    };
  }, [appendOutput]);

  return (
    <div className="terminal-shell">
      <header className="terminal-header">
        <div>
          <span className="terminal-title">Workspace Shell</span>
          <span
            className={`terminal-status terminal-status--${status}`}
            aria-label={`terminal status: ${status}`}
          >
            {status === "connecting" && "Connecting"}
            {status === "ready" && "Connected"}
            {status === "error" && "Stopped"}
          </span>
        </div>
        <div className="terminal-actions">
          <button
            type="button"
            onClick={() => {
              bufferRef.current.clear();
              termRef.current?.reset();
            }}
          >
            Clear
          </button>
          <button
            type="button"
            onClick={() => {
              setDgMode((prev) => !prev);
            }}
            className={dgMode ? "active" : undefined}
          >
            DG Mode
          </button>
        </div>
      </header>
      <div className="terminal-container" ref={containerRef} />
    </div>
  );
});

Terminal.displayName = "Terminal";

export default Terminal;
