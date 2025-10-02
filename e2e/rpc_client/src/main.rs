use std::path::PathBuf;
use std::time::{Duration, Instant};

use anyhow::{anyhow, Context, Result};
use clap::{Parser, Subcommand};
use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, AsyncRead, AsyncWrite, AsyncWriteExt, BufReader};
use tokio::net::TcpStream;
#[cfg(target_family = "unix")]
use tokio::net::UnixStream;
use tokio::time::timeout;

#[cfg(target_os = "windows")]
use tokio::time::sleep;

#[cfg(target_os = "windows")]
use tokio_named_pipes::{ClientOptions, NamedPipeClient};

const DEFAULT_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug, Parser)]
#[command(author, version, about = "Minimal RPC client for DG Core", long_about = None)]
struct Cli {
    /// Path to the Unix domain socket exposed by the daemon
    #[arg(long, value_name = "PATH")]
    socket: Option<PathBuf>,

    /// Name of the Windows named pipe exposed by the daemon
    #[arg(long, value_name = "NAME")]
    pipe: Option<String>,

    /// TCP endpoint exposed by the daemon (host:port)
    #[arg(long, value_name = "ADDR")]
    tcp: Option<String>,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    /// Invoke a JSON-RPC method and emit the response
    Call {
        /// Method name to invoke
        method: String,
        /// JSON object to pass as params. Defaults to an empty object
        #[arg(long)]
        params: Option<String>,
    },
    /// Subscribe to core.tail_logs and stream notifications
    TailLogs {
        /// Stop after collecting this many log notifications
        #[arg(long, value_name = "N")]
        max_events: Option<usize>,
        /// Exit after this many milliseconds even if the stream is still active
        #[arg(long, value_name = "MS", default_value_t = 3000)]
        duration_ms: u64,
    },
}

#[derive(Debug, Clone)]
enum Endpoint {
    #[cfg(target_family = "unix")]
    Unix(PathBuf),
    Tcp(String),
    #[cfg(target_os = "windows")]
    Pipe(String),
}

impl Endpoint {
    fn from_cli(
        socket: Option<PathBuf>,
        tcp: Option<String>,
        pipe: Option<String>,
    ) -> Result<Self> {
        #[allow(unused_mut)]
        let mut selected: Option<Self> = None;

        if let Some(path) = socket {
            if selected.is_some() {
                return Err(anyhow!("specify only one transport"));
            }
            #[cfg(target_family = "unix")]
            {
                selected = Some(Endpoint::Unix(path));
            }
            #[cfg(not(target_family = "unix"))]
            {
                return Err(anyhow!("unix sockets are not supported on this platform"));
            }
        }

        if let Some(addr) = tcp {
            if selected.is_some() {
                return Err(anyhow!("specify only one transport"));
            }
            selected = Some(Endpoint::Tcp(addr));
        }

        #[cfg(target_os = "windows")]
        if let Some(pipe_name) = pipe {
            if selected.is_some() {
                return Err(anyhow!("specify only one transport"));
            }
            selected = Some(Endpoint::Pipe(pipe_name));
        }

        #[cfg(not(target_os = "windows"))]
        if pipe.is_some() {
            return Err(anyhow!("named pipes are only supported on windows"));
        }

        selected.ok_or_else(|| anyhow!("an endpoint must be provided"))
    }
}

#[tokio::main(flavor = "multi_thread")]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    let endpoint = Endpoint::from_cli(cli.socket, cli.tcp, cli.pipe)?;

    match cli.command {
        Commands::Call { method, params } => {
            let value = params
                .map(|payload| serde_json::from_str::<Value>(&payload))
                .transpose()
                .context("failed to parse params JSON")?
                .unwrap_or_else(|| Value::Object(Default::default()));
            let response = call_method(&endpoint, &method, value).await?;
            println!("{}", response);
        }
        Commands::TailLogs {
            max_events,
            duration_ms,
        } => {
            tail_logs(&endpoint, max_events, Duration::from_millis(duration_ms)).await?;
        }
    }

    Ok(())
}

async fn call_method(endpoint: &Endpoint, method: &str, params: Value) -> Result<String> {
    match endpoint {
        #[cfg(target_family = "unix")]
        Endpoint::Unix(path) => {
            let stream = timeout(DEFAULT_TIMEOUT, UnixStream::connect(path))
                .await
                .context("unix socket connection timed out")??;
            call_with_stream(stream, method, params).await
        }
        Endpoint::Tcp(addr) => {
            let stream = timeout(DEFAULT_TIMEOUT, TcpStream::connect(addr))
                .await
                .with_context(|| format!("tcp connect to {addr} timed out"))??;
            call_with_stream(stream, method, params).await
        }
        #[cfg(target_os = "windows")]
        Endpoint::Pipe(name) => {
            let stream = connect_named_pipe(name, DEFAULT_TIMEOUT).await?;
            call_with_stream(stream, method, params).await
        }
    }
}

async fn tail_logs(
    endpoint: &Endpoint,
    max_events: Option<usize>,
    duration: Duration,
) -> Result<()> {
    match endpoint {
        #[cfg(target_family = "unix")]
        Endpoint::Unix(path) => {
            let stream = timeout(DEFAULT_TIMEOUT, UnixStream::connect(path))
                .await
                .context("unix socket connection timed out")??;
            tail_with_stream(stream, max_events, duration).await
        }
        Endpoint::Tcp(addr) => {
            let stream = timeout(DEFAULT_TIMEOUT, TcpStream::connect(addr))
                .await
                .with_context(|| format!("tcp connect to {addr} timed out"))??;
            tail_with_stream(stream, max_events, duration).await
        }
        #[cfg(target_os = "windows")]
        Endpoint::Pipe(name) => {
            let stream = connect_named_pipe(name, DEFAULT_TIMEOUT).await?;
            tail_with_stream(stream, max_events, duration).await
        }
    }
}

async fn call_with_stream<S>(mut stream: S, method: &str, params: Value) -> Result<String>
where
    S: AsyncRead + AsyncWrite + Unpin,
{
    let payload = json!({
        "jsonrpc": "2.0",
        "id": "dg-e2e",
        "method": method,
        "params": params,
    });
    let mut message = serde_json::to_vec(&payload)?;
    if !message.ends_with(b"\n") {
        message.push(b'\n');
    }

    stream.write_all(&message).await?;
    stream.flush().await?;

    let mut reader = BufReader::new(stream);
    let mut line = String::new();
    let read = reader.read_line(&mut line).await?;
    if read == 0 {
        return Err(anyhow!("connection closed before response"));
    }

    Ok(line.trim().to_string())
}

async fn tail_with_stream<S>(
    mut stream: S,
    max_events: Option<usize>,
    duration: Duration,
) -> Result<()>
where
    S: AsyncRead + AsyncWrite + Unpin,
{
    let payload = json!({
        "jsonrpc": "2.0",
        "id": "dg-e2e-tail",
        "method": "core.tail_logs",
        "params": {},
    });
    let mut message = serde_json::to_vec(&payload)?;
    if !message.ends_with(b"\n") {
        message.push(b'\n');
    }

    stream.write_all(&message).await?;
    stream.flush().await?;

    let mut reader = BufReader::new(stream);
    let mut line = String::new();
    let mut seen = 0usize;
    let deadline = Instant::now() + duration;

    loop {
        line.clear();
        let now = Instant::now();
        if now >= deadline {
            break;
        }
        let remaining = deadline - now;
        match timeout(remaining, reader.read_line(&mut line)).await {
            Ok(Ok(0)) => break,
            Ok(Ok(_)) => {
                let trimmed = line.trim_end();
                if trimmed.is_empty() {
                    continue;
                }
                println!("{}", trimmed);
                if let Ok(value) = serde_json::from_str::<Value>(trimmed) {
                    if value
                        .get("method")
                        .and_then(Value::as_str)
                        .map(|method| method == "core.log")
                        .unwrap_or(false)
                    {
                        seen += 1;
                        if let Some(limit) = max_events {
                            if seen >= limit {
                                break;
                            }
                        }
                    }
                }
            }
            Ok(Err(err)) => return Err(err.into()),
            Err(_) => break,
        }
    }

    Ok(())
}

#[cfg(target_os = "windows")]
async fn connect_named_pipe(name: &str, timeout_duration: Duration) -> Result<NamedPipeClient> {
    let deadline = Instant::now() + timeout_duration;
    let pipe_name = if name.starts_with(r"\\.\pipe\") {
        name.to_string()
    } else {
        format!(r"\\.\pipe\{}", name)
    };

    loop {
        match ClientOptions::new().open(&pipe_name) {
            Ok(client) => return Ok(client),
            Err(err) => {
                if Instant::now() >= deadline {
                    return Err(anyhow!("failed to open named pipe {pipe_name}: {err}"));
                }
                sleep(Duration::from_millis(100)).await;
            }
        }
    }
}
