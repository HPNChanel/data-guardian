import { invoke } from "@tauri-apps/api/core";

export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

export type TransportKind = "auto" | "unix" | "namedpipe" | "tcp";
export type ThemePreference = "system" | "light" | "dark";

export interface UserSettings {
  transport: TransportKind;
  endpoint?: string | null;
  theme: ThemePreference;
  allow_network: boolean;
}

export interface RpcEnvelope<T = JsonValue> {
  id: string;
  result?: T;
  error?: JsonValue;
}

export interface ScanFinding {
  id: string;
  label: string;
  start: number;
  end: number;
  score?: number;
  snippet?: string;
  remediation?: string;
}

export interface ScanResult {
  findings: ScanFinding[];
  summary?: {
    total: number;
    redacted?: number;
    severity?: Record<string, number>;
    elapsed_ms?: number;
  };
}

export interface RedactResult {
  redacted: string;
  diff?: Array<{
    kind: "context" | "removed" | "added";
    value: string;
  }>;
  download_name?: string;
}

export interface PolicyResult {
  policy: JsonValue;
  applied_at?: string;
}

interface RpcRequest {
  method: string;
  params?: JsonValue;
  timeoutMs?: number;
}

export async function dgRpc<T = JsonValue>({
  method,
  params,
  timeoutMs,
}: RpcRequest): Promise<T> {
  const response = await invoke<RpcEnvelope<T | undefined>>("dg_rpc", {
    method,
    params,
    timeoutMs,
  });

  if (response.error !== undefined && response.error !== null) {
    const message =
      typeof response.error === "string"
        ? response.error
        : JSON.stringify(response.error);
    throw new Error(message || `DG RPC call '${method}' failed`);
  }

  if (response.result === undefined) {
    throw new Error(`DG RPC '${method}' returned no result`);
  }

  return response.result;
}

export async function scanText(input: string, extra?: Record<string, JsonValue>) {
  const params = { text: input, ...(extra ?? {}) };
  const result = await dgRpc<ScanResult>({
    method: "scan_text",
    params,
    timeoutMs: 15_000,
  });
  return result;
}

export async function scanFile(filePath: string, extra?: Record<string, JsonValue>) {
  const params = { path: filePath, ...(extra ?? {}) };
  const result = await dgRpc<ScanResult>({
    method: "scan_file",
    params,
    timeoutMs: 30_000,
  });
  return result;
}

export async function redactText(input: string, extra?: Record<string, JsonValue>) {
  const params = { text: input, ...(extra ?? {}) };
  const result = await dgRpc<RedactResult>({
    method: "redact_text",
    params,
    timeoutMs: 20_000,
  });
  return result;
}

export async function redactFile(filePath: string, extra?: Record<string, JsonValue>) {
  const params = { path: filePath, ...(extra ?? {}) };
  const result = await dgRpc<RedactResult>({
    method: "redact_file",
    params,
    timeoutMs: 35_000,
  });
  return result;
}

export async function fetchPolicy(): Promise<PolicyResult> {
  return dgRpc<PolicyResult>({ method: "get_policy", timeoutMs: 5_000 });
}

export async function applyPolicy(policy: JsonValue) {
  return dgRpc<PolicyResult>({
    method: "set_policy",
    params: { policy },
    timeoutMs: 7_000,
  });
}

export async function loadSettings() {
  return invoke<UserSettings>("load_settings");
}

export async function saveSettings(settings: UserSettings) {
  return invoke<void>("save_settings", { updated: settings });
}

export async function checkUpdates() {
  return invoke<string>("dg_check_updates");
}
