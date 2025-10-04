use std::collections::VecDeque;
use std::sync::Arc;
use std::time::Duration;

use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};
use tokio::net::TcpStream;
use tokio::sync::Mutex;
use tokio::time::timeout;

#[cfg(target_os = "windows")]
use tokio::net::windows::named_pipe::ClientOptions;
#[cfg(target_os = "windows")]
use tokio::net::windows::named_pipe::NamedPipeClient;
#[cfg(target_family = "unix")]
use tokio::net::UnixStream;

use super::transport::Endpoint;

const DEFAULT_TIMEOUT: Duration = Duration::from_millis(5_000);
const DEFAULT_RETRIES: usize = 1;

#[derive(Debug, Clone)]
pub struct BridgeConfig {
    pub endpoints: Vec<Endpoint>,
    pub timeout: Duration,
    pub retries: usize,
}

impl BridgeConfig {
    pub fn new(endpoints: Vec<Endpoint>) -> Self {
        Self {
            endpoints,
            timeout: DEFAULT_TIMEOUT,
            retries: DEFAULT_RETRIES,
        }
    }

    pub fn with_timeout(mut self, timeout: Duration) -> Self {
        self.timeout = timeout;
        self
    }

    pub fn with_retries(mut self, retries: usize) -> Self {
        self.retries = retries;
        self
    }
}

#[derive(Debug, Clone)]
pub struct RpcRequest {
    pub id: String,
    pub method: String,
    pub params: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RpcResponse {
    pub id: String,
    #[serde(default)]
    pub result: Option<serde_json::Value>,
    #[serde(default)]
    pub error: Option<serde_json::Value>,
}

#[derive(Clone)]
pub struct BridgeClient {
    endpoints: Vec<Endpoint>,
    timeout: Duration,
    retries: usize,
    active_endpoint: Arc<Mutex<Option<Endpoint>>>,
}

impl BridgeClient {
    pub async fn connect(config: BridgeConfig) -> Result<Self> {
        if config.endpoints.is_empty() {
            return Err(anyhow!("bridge config requires at least one endpoint"));
        }

        let mut unique = Vec::new();
        for endpoint in config.endpoints {
            if !unique.contains(&endpoint) {
                unique.push(endpoint);
            }
        }

        let client = Self {
            endpoints: unique.clone(),
            timeout: config.timeout,
            retries: config.retries.max(1),
            active_endpoint: Arc::new(Mutex::new(None)),
        };

        for endpoint in &client.endpoints {
            if Self::probe_endpoint(endpoint, client.timeout).await.is_ok() {
                *client.active_endpoint.lock().await = Some(endpoint.clone());
                return Ok(client);
            }
        }

        Err(anyhow!(
            "failed to reach DG Core on any configured endpoint"
        ))
    }

    pub async fn send_request(&self, request: RpcRequest) -> Result<RpcResponse> {
        let payload = serde_json::json!({
            "jsonrpc": "2.0",
            "id": request.id,
            "method": request.method,
            "params": request.params.unwrap_or(serde_json::Value::Null),
        });
        let mut envelope = serde_json::to_vec(&payload)?;
        if !envelope.ends_with(b"\n") {
            envelope.push(b'\n');
        }

        let mut candidates = VecDeque::new();
        if let Some(active) = self.active_endpoint.lock().await.clone() {
            candidates.push_back(active);
        }
        for endpoint in &self.endpoints {
            if Some(endpoint) != candidates.front() {
                candidates.push_back(endpoint.clone());
            }
        }

        let mut last_err = None;

        while let Some(endpoint) = candidates.pop_front() {
            for attempt in 0..=self.retries {
                match Self::send_over_endpoint(&endpoint, &envelope, self.timeout).await {
                    Ok(bytes) => {
                        let response: JsonRpcResponse = serde_json::from_slice(&bytes)
                            .with_context(|| {
                                format!("invalid json-rpc response from {}", endpoint)
                            })?;
                        let rpc = response.into_rpc()?;
                        *self.active_endpoint.lock().await = Some(endpoint.clone());
                        return Ok(rpc);
                    }
                    Err(err) => {
                        last_err =
                            Some(err.context(format!("attempt {attempt} via {} failed", endpoint)));
                        tokio::time::sleep(Duration::from_millis(50)).await;
                    }
                }
            }
        }

        Err(last_err.unwrap_or_else(|| anyhow!("request dispatch failed")))
    }

    pub async fn probe_endpoint(endpoint: &Endpoint, timeout_duration: Duration) -> Result<()> {
        match endpoint {
            Endpoint::Tcp(addr) => {
                timeout(timeout_duration, TcpStream::connect(addr))
                    .await
                    .context("tcp connect timed out")??;
                Ok(())
            }
            Endpoint::Unix(path) => {
                #[cfg(target_family = "unix")]
                {
                    timeout(timeout_duration, UnixStream::connect(path))
                        .await
                        .with_context(|| {
                            format!("unix connect to {} timed out", path.display())
                        })??;
                    Ok(())
                }
                #[cfg(not(target_family = "unix"))]
                {
                    let _ = path;
                    Err(anyhow!("unix sockets not supported on this platform"))
                }
            }
            Endpoint::NamedPipe(name) => {
                #[cfg(target_os = "windows")]
                {
                    ClientOptions::new()
                        .open(name)
                        .with_context(|| format!("failed to open named pipe {name}"))?;
                    Ok(())
                }
                #[cfg(not(target_os = "windows"))]
                {
                    let _ = name;
                    Err(anyhow!("named pipes are only supported on windows"))
                }
            }
        }
    }

    async fn send_over_endpoint(
        endpoint: &Endpoint,
        message: &[u8],
        timeout_duration: Duration,
    ) -> Result<Vec<u8>> {
        match endpoint {
            Endpoint::Tcp(addr) => {
                let mut stream = timeout(timeout_duration, TcpStream::connect(addr))
                    .await
                    .context("tcp connect timed out")??;
                Self::exchange(&mut stream, message, timeout_duration).await
            }
            Endpoint::Unix(path) => {
                #[cfg(target_family = "unix")]
                {
                    let mut stream = timeout(timeout_duration, UnixStream::connect(path))
                        .await
                        .with_context(|| {
                            format!("unix connect to {} timed out", path.display())
                        })??;
                    Self::exchange(&mut stream, message, timeout_duration).await
                }
                #[cfg(not(target_family = "unix"))]
                {
                    let _ = path;
                    Err(anyhow!("unix sockets not supported on this platform"))
                }
            }
            Endpoint::NamedPipe(name) => {
                #[cfg(target_os = "windows")]
                {
                    let mut client: NamedPipeClient = ClientOptions::new()
                        .open(name)
                        .with_context(|| format!("failed to open named pipe {name}"))?;
                    Self::exchange(&mut client, message, timeout_duration).await
                }
                #[cfg(not(target_os = "windows"))]
                {
                    let _ = name;
                    Err(anyhow!("named pipes are only supported on windows"))
                }
            }
        }
    }

    async fn exchange<S>(
        stream: &mut S,
        message: &[u8],
        timeout_duration: Duration,
    ) -> Result<Vec<u8>>
    where
        S: AsyncRead + AsyncWrite + Unpin + Send,
    {
        let mut response = Vec::with_capacity(512);
        let payload = message.to_vec();

        timeout(timeout_duration, async {
            if !payload.is_empty() {
                stream.write_all(&payload).await?;
                if !payload.ends_with(b"\n") {
                    stream.write_all(b"\n").await?;
                }
                stream.flush().await?;
            }

            let mut buf = [0u8; 512];
            loop {
                let read = stream.read(&mut buf).await?;
                if read == 0 {
                    break;
                }
                response.extend_from_slice(&buf[..read]);
                if response.ends_with(b"\n") {
                    break;
                }
            }

            Ok::<_, anyhow::Error>(())
        })
        .await
        .context("io exchange timed out")??;

        if response.is_empty() {
            return Err(anyhow!("empty response"));
        }

        while response.last() == Some(&b'\n') || response.last() == Some(&b'\r') {
            response.pop();
        }

        Ok(response)
    }
}

#[allow(dead_code)]
#[derive(Debug, Deserialize)]
struct JsonRpcResponse {
    #[serde(default)]
    jsonrpc: Option<String>,
    id: serde_json::Value,
    #[serde(default)]
    result: Option<serde_json::Value>,
    #[serde(default)]
    error: Option<serde_json::Value>,
}

impl JsonRpcResponse {
    fn into_rpc(self) -> Result<RpcResponse> {
        let id = match self.id {
            serde_json::Value::String(s) => s,
            value => value.to_string(),
        };

        if self.result.is_none() && self.error.is_none() {
            return Err(anyhow!("json-rpc response missing result and error"));
        }

        Ok(RpcResponse {
            id,
            result: self.result,
            error: self.error,
        })
    }
}
