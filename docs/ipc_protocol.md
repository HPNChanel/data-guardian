# DG Core IPC Protocol

The DG Core daemon exposes a JSON-RPC 2.0 compatible interface over a local
inter-process communication (IPC) channel. The daemon is intended to run in the
background and is launched by the desktop application.

## Transport

| Platform | Endpoint |
| --- | --- |
| macOS | Unix domain socket at `~/Library/Application Support/Data Guardian/ipc/dg-core.sock` |
| Linux | Unix domain socket at `~/.config/data-guardian/ipc/dg-core.sock` |
| Windows | Named pipe `\\.\\pipe\\data_guardian_core` |

The daemon listens for newline-delimited JSON messages. Each message MUST be a
single JSON object representing a JSON-RPC request or notification.

## Message Structure

Requests follow standard JSON-RPC 2.0 semantics:

```json
{ "jsonrpc": "2.0", "id": 1, "method": "core.ping", "params": { ... } }
```

Responses:

```json
{ "jsonrpc": "2.0", "id": 1, "result": { ... } }
```

Errors are reported using the JSON-RPC `error` object:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": { "code": -32602, "message": "Invalid params", "data": { ... } }
}
```

Notifications omit the `id` field. The daemon sends notifications to deliver
log events using the `core.log` method.

## Limits and Timeouts

* Maximum request size: 512 KiB.
* Per-request read timeout: 15 seconds.
* Requests exceeding these limits receive an error response and are ignored.

## Methods

### `core.ping`

Health check returning version information.

**Response**

```json
{ "ok": true, "version": "<semver>" }
```

### `core.scan_path`

Scan a file for detections.

**Params**

| Name | Type | Description |
| --- | --- | --- |
| `path` | string | Absolute or relative path to the file. |
| `detectors` | array\[string] | Optional detector filters. |
| `max_results` | integer | Optional maximum number of detections. |

**Response**

```json
{ "path": "...", "detections": [ { ... } ] }
```

### `core.redact_file`

Redact a file using an optional policy.

**Params**

| Name | Type | Description |
| --- | --- | --- |
| `path` | string | Input file path. |
| `output_path` | string | Optional path to write the redacted content. |
| `policy_path` | string | Optional policy file. |
| `policy` | object | Optional inline policy (mutually exclusive with `policy_path`). |

**Response**

```json
{
  "path": "...",
  "output": "...",        // UTF-8 text representation
  "segments": [ { ... } ],
  "written_to": "..."     // Path where the output was written, when requested
}
```

### `core.load_policy`

Load and validate a policy file.

**Params**: `{ "path": "..." }`

**Response**

```json
{ "path": "...", "policy": { ... } }
```

### `core.test_policy`

Evaluate a policy against a sample input.

**Params**

| Name | Type | Description |
| --- | --- | --- |
| `text` | string | Sample content to scan. |
| `policy_path` | string | Optional policy file. |
| `policy` | object | Optional inline policy. |

**Response**

```json
{
  "detections": [ { ... } ],
  "decisions": [ { "detector": "...", "action": "MASK", "reason": "..." } ],
  "output": "..."   // Redacted sample
}
```

### `core.get_status`

Retrieve daemon runtime metrics.

**Response**

```json
{
  "ok": true,
  "uptime": 12.34,
  "requests": 42,
  "connections": 1,
  "log_subscribers": 0
}
```

### `core.tail_logs`

Subscribe to structured log events. The response acknowledges the subscription
and log entries will be streamed as notifications with method `core.log`.

**Response**

```json
{ "subscribed": true }
```

**Notification Example**

```json
{ "jsonrpc": "2.0", "method": "core.log", "params": { "ts": "...", "level": "info", "msg": "...", "component": "..." } }
```

Log delivery uses bounded queues to prevent runaway memory usage. When
subscribers cannot keep up the oldest log entries are dropped.

## Logging

Logs are emitted as JSON lines with the keys `level`, `ts`, `msg`, and
`component`. Additional context supplied by the daemon is preserved as extra
fields.

## Sample Ping

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"core.ping"}' | socat - UNIX-CONNECT:"$HOME/.config/data-guardian/ipc/dg-core.sock"
```
