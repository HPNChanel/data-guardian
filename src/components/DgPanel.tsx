import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useState } from "react";

import type { ScanFinding, ScanResult } from "../api";
import { applyPolicy, fetchPolicy, redactText, scanFile, scanText } from "../api";

export interface DgPanelHandle {
  scanText: (input: string) => Promise<void>;
  redactText: (input: string) => Promise<void>;
}

type TabKey = "scan" | "redact" | "policy";

interface DiffSegment {
  kind: "context" | "removed" | "added";
  value: string;
}

interface ScanState {
  input: string;
  loading: boolean;
  error?: string;
  result?: ScanResult;
  sourceName?: string;
}

interface RedactState {
  input: string;
  loading: boolean;
  error?: string;
  result?: {
    redacted: string;
    diff: DiffSegment[];
    downloadName: string;
  };
  downloadUrl?: string;
  sourceName?: string;
}

interface PolicyState {
  content: string;
  loading: boolean;
  savedMessage?: string;
  error?: string;
}

const DgPanel = forwardRef<DgPanelHandle>((_, ref) => {
  const [activeTab, setActiveTab] = useState<TabKey>("scan");
  const [scanState, setScanState] = useState<ScanState>({ input: "", loading: false });
  const [redactState, setRedactState] = useState<RedactState>({ input: "", loading: false });
  const [policyState, setPolicyState] = useState<PolicyState>({ content: "", loading: false });

  const runScan = useCallback(
    async (source: string, sourceName?: string) => {
      setActiveTab("scan");
      setScanState((prev) => ({ ...prev, loading: true, error: undefined, input: source, sourceName }));
      try {
        const result = await scanText(source);
        setScanState((prev) => ({ ...prev, loading: false, result }));
      } catch (error) {
        setScanState((prev) => ({
          ...prev,
          loading: false,
          error: (error as Error).message,
        }));
      }
    },
    []
  );

  const runRedact = useCallback(
    async (source: string, sourceName?: string) => {
      setActiveTab("redact");
      setRedactState((prev) => ({ ...prev, loading: true, error: undefined, input: source, sourceName }));
      try {
        const result = await redactText(source);
        const diff = computeDiff(source, result.redacted);
        setRedactState((prev) => ({
          ...prev,
          loading: false,
          result: {
            redacted: result.redacted,
            diff,
            downloadName: result.download_name ?? buildDownloadName(sourceName),
          },
        }));
      } catch (error) {
        setRedactState((prev) => ({
          ...prev,
          loading: false,
          error: (error as Error).message,
        }));
      }
    },
    []
  );

  useImperativeHandle(ref, () => ({
    async scanText(text: string) {
      await runScan(text);
    },
    async redactText(text: string) {
      await runRedact(text);
    },
  }));

  useEffect(() => {
    let cancelled = false;
    const loadPolicy = async () => {
      setPolicyState((prev) => ({ ...prev, loading: true, error: undefined }));
      try {
        const response = await fetchPolicy();
        if (!cancelled) {
          setPolicyState({
            loading: false,
            content: JSON.stringify(response.policy, null, 2),
            savedMessage: undefined,
            error: undefined,
          });
        }
      } catch (error) {
        if (!cancelled) {
          setPolicyState((prev) => ({
            ...prev,
            loading: false,
            error: (error as Error).message,
          }));
        }
      }
    };

    loadPolicy();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (redactState.downloadUrl) {
        URL.revokeObjectURL(redactState.downloadUrl);
      }
    };
  }, [redactState.downloadUrl]);

  const highlightedScan = useMemo(() => {
    if (!scanState.result) {
      return scanState.input;
    }
    return highlightFindings(scanState.input, scanState.result.findings ?? []);
  }, [scanState.input, scanState.result]);

  return (
    <section className="panel">
      <header className="panel-header">
        <nav className="panel-tabs" aria-label="DG tools">
          <button
            type="button"
            className={activeTab === "scan" ? "active" : ""}
            onClick={() => setActiveTab("scan")}
          >
            Scan
          </button>
          <button
            type="button"
            className={activeTab === "redact" ? "active" : ""}
            onClick={() => setActiveTab("redact")}
          >
            Redact
          </button>
          <button
            type="button"
            className={activeTab === "policy" ? "active" : ""}
            onClick={() => setActiveTab("policy")}
          >
            Policy
          </button>
        </nav>
      </header>

      <div className="panel-body">
        {activeTab === "scan" && (
          <div className="panel-section">
            <form
              onSubmit={(event) => {
                event.preventDefault();
                runScan(scanState.input, scanState.sourceName);
              }}
              className="panel-form"
            >
              <textarea
                value={scanState.input}
                onChange={(event) =>
                  setScanState((prev) => ({ ...prev, input: event.target.value }))
                }
                placeholder="Paste text to scan or use Ctrl/Cmd+F in the terminal"
                rows={10}
              />
              <div className="panel-form__actions">
                <label className="panel-upload">
                  <input
                    type="file"
                    accept=".txt,.md,.json,.yaml,.yml"
                    onChange={async (event) => {
                      const file = event.target.files?.[0];
                      if (!file) return;
                      const content = await file.text();
                      setScanState({
                        input: content,
                        loading: false,
                        sourceName: file.name,
                        result: undefined,
                        error: undefined,
                      });
                    }}
                  />
                  Load file
                </label>
                <button type="submit" disabled={scanState.loading}>
                  {scanState.loading ? "Scanning…" : "Run scan"}
                </button>
              </div>
            </form>

            {scanState.error && <p className="panel-error">{scanState.error}</p>}

            {scanState.result && (
              <div className="panel-result">
                <h4>Findings ({scanState.result.findings.length})</h4>
                <pre className="panel-text" aria-live="polite">
                  {highlightedScan}
                </pre>
                <FindingsTable findings={scanState.result.findings} />
              </div>
            )}
          </div>
        )}

        {activeTab === "redact" && (
          <div className="panel-section">
            <form
              onSubmit={(event) => {
                event.preventDefault();
                runRedact(redactState.input, redactState.sourceName);
              }}
              className="panel-form"
            >
              <textarea
                value={redactState.input}
                onChange={(event) =>
                  setRedactState((prev) => ({ ...prev, input: event.target.value }))
                }
                placeholder="Paste text to redact or use Ctrl/Cmd+R in the terminal"
                rows={10}
              />
              <div className="panel-form__actions">
                <label className="panel-upload">
                  <input
                    type="file"
                    accept=".txt,.md,.json,.yaml,.yml"
                    onChange={async (event) => {
                      const file = event.target.files?.[0];
                      if (!file) return;
                      const content = await file.text();
                      setRedactState({
                        input: content,
                        loading: false,
                        result: undefined,
                        error: undefined,
                        sourceName: file.name,
                      });
                    }}
                  />
                  Load file
                </label>
                <button type="submit" disabled={redactState.loading}>
                  {redactState.loading ? "Redacting…" : "Run redact"}
                </button>
              </div>
            </form>

            {redactState.error && <p className="panel-error">{redactState.error}</p>}

            {redactState.result && (
              <div className="panel-result">
                <h4>Redacted output</h4>
                <div className="panel-diff">
                  {redactState.result.diff.map((segment, index) => (
                    <span key={index} className={`diff-segment diff-${segment.kind}`}>
                      {segment.value}
                    </span>
                  ))}
                </div>
                <div className="panel-actions">
                  <button
                    type="button"
                    onClick={() => {
                      const blob = new Blob([redactState.result?.redacted ?? ""], {
                        type: "text/plain",
                      });
                      const url = URL.createObjectURL(blob);
                      const anchor = document.createElement("a");
                      anchor.href = url;
                      anchor.download = redactState.result?.downloadName ?? "redacted.txt";
                      anchor.click();
                      URL.revokeObjectURL(url);
                    }}
                  >
                    Download redacted file
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "policy" && (
          <div className="panel-section">
            <form
              onSubmit={async (event) => {
                event.preventDefault();
                setPolicyState((prev) => ({ ...prev, loading: true, error: undefined, savedMessage: undefined }));
                try {
                  const parsed = policyState.content ? JSON.parse(policyState.content) : {};
                  await applyPolicy(parsed);
                  setPolicyState((prev) => ({
                    ...prev,
                    loading: false,
                    savedMessage: "Policy updated",
                  }));
                } catch (error) {
                  setPolicyState((prev) => ({
                    ...prev,
                    loading: false,
                    error: (error as Error).message,
                  }));
                }
              }}
              className="panel-form"
            >
              <textarea
                value={policyState.content}
                onChange={(event) =>
                  setPolicyState((prev) => ({ ...prev, content: event.target.value }))
                }
                rows={12}
                placeholder="Paste DG policy JSON"
              />
              <div className="panel-form__actions">
                <button type="submit" disabled={policyState.loading}>
                  {policyState.loading ? "Saving…" : "Save policy"}
                </button>
              </div>
            </form>
            {policyState.error && <p className="panel-error">{policyState.error}</p>}
            {policyState.savedMessage && <p className="panel-success">{policyState.savedMessage}</p>}
          </div>
        )}
      </div>
    </section>
  );
});

DgPanel.displayName = "DgPanel";

export default DgPanel;

interface FindingsTableProps {
  findings: ScanFinding[];
}

const FindingsTable = ({ findings }: FindingsTableProps) => {
  if (!findings.length) {
    return <p className="panel-empty">No findings detected.</p>;
  }

  return (
    <table className="panel-table">
      <thead>
        <tr>
          <th>Label</th>
          <th>Position</th>
          <th>Score</th>
          <th>Snippet</th>
        </tr>
      </thead>
      <tbody>
        {findings.map((finding) => (
          <tr key={finding.id}>
            <td>{finding.label}</td>
            <td>
              {finding.start}?{finding.end}
            </td>
            <td>{finding.score?.toFixed(2) ?? "–"}</td>
            <td>{finding.snippet ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};

function highlightFindings(text: string, findings: ScanFinding[]) {
  if (!findings.length) {
    return text;
  }

  const segments: Array<string | JSX.Element> = [];
  let cursor = 0;
  const ordered = [...findings].sort((a, b) => a.start - b.start);

  ordered.forEach((finding, index) => {
    if (finding.start > cursor) {
      segments.push(text.slice(cursor, finding.start));
    }
    const value = text.slice(finding.start, finding.end);
    segments.push(
      <mark key={`${finding.id}-${index}`} className="panel-highlight">
        {value}
      </mark>
    );
    cursor = finding.end;
  });

  if (cursor < text.length) {
    segments.push(text.slice(cursor));
  }

  return segments;
}

function computeDiff(original: string, redacted: string): DiffSegment[] {
  if (original === redacted) {
    return [{ kind: "context", value: original }];
  }

  let prefix = 0;
  const minLength = Math.min(original.length, redacted.length);
  while (prefix < minLength && original[prefix] === redacted[prefix]) {
    prefix += 1;
  }

  let suffixOriginal = original.length;
  let suffixRedacted = redacted.length;
  while (
    suffixOriginal > prefix &&
    suffixRedacted > prefix &&
    original[suffixOriginal - 1] === redacted[suffixRedacted - 1]
  ) {
    suffixOriginal -= 1;
    suffixRedacted -= 1;
  }

  const segments: DiffSegment[] = [];
  const contextPrefix = original.slice(0, prefix);
  if (contextPrefix) {
    segments.push({ kind: "context", value: contextPrefix });
  }

  const removed = original.slice(prefix, suffixOriginal);
  if (removed) {
    segments.push({ kind: "removed", value: removed });
  }

  const added = redacted.slice(prefix, suffixRedacted);
  if (added) {
    segments.push({ kind: "added", value: added });
  }

  const contextSuffix = redacted.slice(suffixRedacted);
  if (contextSuffix) {
    segments.push({ kind: "context", value: contextSuffix });
  }

  return segments;
}

function buildDownloadName(source?: string) {
  if (!source) {
    return "redacted.txt";
  }
  const dot = source.lastIndexOf(".");
  if (dot === -1) {
    return `${source}.redacted.txt`;
  }
  return `${source.slice(0, dot)}.redacted${source.slice(dot)}`;
}
