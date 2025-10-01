use std::path::{Path, PathBuf};

use anyhow::Context;
use once_cell::sync::OnceCell;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::{AppHandle, State, Window};
use thiserror::Error;
use tokio::sync::Mutex;

#[cfg(unix)]
use tokio::net::{UnixListener, UnixStream};
#[cfg(unix)]
use tokio::{fs, io::{AsyncBufReadExt, AsyncWriteExt, BufReader}};
#[cfg(unix)]
use tokio::task::JoinHandle;

#[cfg(windows)]
use tokio::task::JoinHandle;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct BridgeConfig {
    #[serde(default)]
    pub socket_path: Option<String>,
    #[serde(default)]
    pub log_level: Option<String>,
}

#[derive(Default)]
pub struct BridgeState {
    inner: Mutex<BridgeInner>,
}

#[derive(Default)]
struct BridgeInner {
    #[cfg(unix)]
    endpoint: Option<PathBuf>,
    #[cfg(windows)]
    endpoint: Option<String>,
    log_level: Option<String>,
    mock_handle: Option<JoinHandle<()>>,
}

static LOG_BROADCAST: OnceCell<tokio::sync::broadcast::Sender<String>> = OnceCell::new();

#[derive(Debug, Error)]
pub enum BridgeError {
    #[error("bridge not initialized")] 
    NotInitialized,
    #[error("transport error: {0}")]
    Transport(String),
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

type Result<T> = std::result::Result<T, BridgeError>;

impl BridgeState {
    pub fn new() -> Self {
        Self::default()
    }
}

#[tauri::command]
pub async fn init_core(state: State<'_, BridgeState>, config: Option<BridgeConfig>) -> std::result::Result<(), String> {
    let mut guard = state.inner.lock().await;
    if let Some(cfg) = config {
        if let Some(path) = cfg.socket_path.as_deref().filter(|p| !p.is_empty()) {
            guard.endpoint = Some(resolve_endpoint(path));
        } else {
            guard.endpoint = Some(default_endpoint());
        }
        guard.log_level = cfg.log_level.clone();
    } else if guard.endpoint.is_none() {
        guard.endpoint = Some(default_endpoint());
    }

    if guard.mock_handle.is_none() {
        #[cfg(unix)]
        {
            if let Some(path) = guard.endpoint.clone() {
                match spawn_mock_core(&path).await {
                    Ok(handle) => guard.mock_handle = Some(handle),
                    Err(error) => return Err(error.to_string()),
                }
            }
        }
        #[cfg(windows)]
        {
            let endpoint = guard.endpoint.clone().unwrap_or_else(default_endpoint);
            guard.mock_handle = Some(spawn_mock_core_windows(endpoint));
        }
    }

    Ok(())
}

#[tauri::command]
pub async fn send_request(state: State<'_, BridgeState>, payload: Value) -> std::result::Result<Value, String> {
    let guard = state.inner.lock().await;
    let endpoint = guard.endpoint.clone().ok_or_else(|| BridgeError::NotInitialized.to_string())?;
    drop(guard);

    #[cfg(unix)]
    {
        match send_request_unix(&endpoint, payload).await {
            Ok(value) => Ok(value),
            Err(error) => Err(error.to_string()),
        }
    }
    #[cfg(windows)]
    {
        match send_request_windows(&endpoint, payload).await {
            Ok(value) => Ok(value),
            Err(error) => Err(error.to_string()),
        }
    }
}

#[tauri::command]
pub async fn subscribe_logs(window: Window) -> std::result::Result<(), String> {
    let sender = if let Some(existing) = LOG_BROADCAST.get() {
        existing.clone()
    } else {
        let (tx, _) = tokio::sync::broadcast::channel(256);
        let _ = LOG_BROADCAST.set(tx.clone());
        tx
    };

    let mut receiver = sender.subscribe();
    tauri::async_runtime::spawn(async move {
        while let Ok(line) = receiver.recv().await {
            let _ = window.emit("core://log", line);
        }
    });

    Ok(())
}

#[cfg(unix)]
fn resolve_endpoint(path: &str) -> PathBuf {
    PathBuf::from(path)
}

#[cfg(windows)]
fn resolve_endpoint(path: &str) -> String {
    path.to_string()
}

#[cfg(unix)]
fn default_endpoint() -> PathBuf {
    std::env::temp_dir().join("dg-core.sock")
}

#[cfg(windows)]
fn default_endpoint() -> String {
    r"\\.\pipe\dg-core".to_string()
}

#[cfg(unix)]
async fn send_request_unix(path: &Path, payload: Value) -> Result<Value> {
    use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};

    let message = serde_json::to_string(&payload).context("serializing request")?;
    let mut stream = UnixStream::connect(path)
        .await
        .map_err(|error| BridgeError::Transport(error.to_string()))?;

    stream
        .write_all(message.as_bytes())
        .await
        .map_err(|error| BridgeError::Transport(error.to_string()))?;
    stream
        .write_all(b"\n")
        .await
        .map_err(|error| BridgeError::Transport(error.to_string()))?;
    stream
        .flush()
        .await
        .map_err(|error| BridgeError::Transport(error.to_string()))?;

    let mut reader = BufReader::new(stream);
    let mut response = String::new();
    reader
        .read_line(&mut response)
        .await
        .map_err(|error| BridgeError::Transport(error.to_string()))?;
    if response.is_empty() {
        return Err(BridgeError::Transport("empty response".into()));
    }

    let json: Value = serde_json::from_str(response.trim_end()).context("parsing response")?;
    Ok(json)
}

#[cfg(windows)]
async fn send_request_windows(_pipe: &str, payload: Value) -> Result<Value> {
    let response = serde_json::json!({
        "status": "ok",
        "echo": payload,
        "platform": "windows-stub"
    });
    Ok(response)
}

#[cfg(unix)]
async fn spawn_mock_core(path: &Path) -> anyhow::Result<JoinHandle<()>> {
    if path.exists() {
        fs::remove_file(path).await.ok();
    }

    let listener = UnixListener::bind(path).context("binding unix socket")?;
    let (sender, _) = tokio::sync::broadcast::channel(256);
    let _ = LOG_BROADCAST.set(sender.clone());

    let handle = tauri::async_runtime::spawn(async move {
        let _ = sender.send(format!("[mock-core] listening on {}", path.display()));
        loop {
            match listener.accept().await {
                Ok((stream, _)) => {
                    let tx = sender.clone();
                    tauri::async_runtime::spawn(async move {
                        let mut reader = BufReader::new(stream);
                        let mut buffer = String::new();
                        if reader.read_line(&mut buffer).await.is_err() {
                            return;
                        }
                        let trimmed = buffer.trim_end().to_string();
                        let _ = tx.send(format!("[mock-core] received: {}", trimmed));
                        let response = match serde_json::from_str::<Value>(&trimmed) {
                            Ok(request) => {
                                let action = request.get("action").and_then(Value::as_str).unwrap_or("unknown");
                                serde_json::json!({
                                    "status": "ok",
                                    "action": action,
                                    "echo": request,
                                })
                            }
                            Err(error) => {
                                serde_json::json!({
                                    "status": "error",
                                    "message": format!("invalid json: {error}")
                                })
                            }
                        };
                        let response_text = format!("{}\n", response.to_string());
                        let mut inner_stream = reader.into_inner();
                        let _ = inner_stream.write_all(response_text.as_bytes()).await;
                        let _ = inner_stream.flush().await;
                        let _ = tx.send(format!("[mock-core] responded with: {}", response));
                    });
                }
                Err(error) => {
                    let _ = sender.send(format!("[mock-core] listener error: {error}"));
                    break;
                }
            }
        }
    });

    Ok(handle)
}

#[cfg(windows)]
fn spawn_mock_core_windows(endpoint: String) -> JoinHandle<()> {
    let (sender, _) = tokio::sync::broadcast::channel(256);
    let _ = LOG_BROADCAST.set(sender.clone());
    tauri::async_runtime::spawn(async move {
        let _ = sender.send(format!("[mock-core] windows stub listening on {endpoint}"));
    })
}

pub fn manage_state(app: &AppHandle) {
    app.manage(BridgeState::new());
}
