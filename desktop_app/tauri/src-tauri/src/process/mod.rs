use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::{Duration, Instant};

use anyhow::{anyhow, Context, Result};
use directories::ProjectDirs;
use tokio::io::{AsyncBufReadExt, AsyncRead, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::Mutex;

use crate::bridge::{BridgeClient, Endpoint};

#[derive(Debug, Clone)]
pub struct ProcessConfig {
    pub binary: PathBuf,
    pub runtime_dir: PathBuf,
    pub socket_endpoint: Endpoint,
    pub tcp_fallback: Option<Endpoint>,
    pub allow_network: bool,
    pub extra_args: Vec<String>,
}

impl Default for ProcessConfig {
    fn default() -> Self {
        let project_dirs = ProjectDirs::from("com", "dataguardian", "DataGuardianDesktop")
            .expect("unable to resolve project directories");
        let data_dir = project_dirs.data_dir().to_path_buf();
        let ipc_dir = data_dir.join("ipc");

        #[cfg(target_os = "windows")]
        let socket_endpoint = Endpoint::NamedPipe(r"\\.\pipe\data_guardian_core".to_string());

        #[cfg(not(target_os = "windows"))]
        let socket_endpoint = Endpoint::Unix(ipc_dir.join("dg-core.sock"));

        let tcp_fallback = Some(Endpoint::Tcp(
            "127.0.0.1:7878"
                .parse()
                .expect("valid tcp fallback address"),
        ));

        Self {
            binary: PathBuf::from("dg"),
            runtime_dir: data_dir,
            socket_endpoint,
            tcp_fallback,
            allow_network: false,
            extra_args: Vec::new(),
        }
    }
}

struct ProcessState {
    child: Option<Child>,
}

pub struct ProcessManager {
    config: Mutex<ProcessConfig>,
    state: Mutex<ProcessState>,
}

impl ProcessManager {
    pub fn new(config: ProcessConfig) -> Self {
        Self {
            config: Mutex::new(config),
            state: Mutex::new(ProcessState { child: None }),
        }
    }

    pub async fn ensure_running(&self) -> Result<()> {
        let mut state = self.state.lock().await;

        if let Some(child) = state.child.as_mut() {
            if child.try_wait()?.is_none() {
                drop(state);
                self.wait_for_ready().await?;
                return Ok(());
            }
        }

        let config = self.config.lock().await.clone();
        let mut child = spawn_core(&config).await?;
        pipe_logs(child.stdout.take(), "dg-core stdout");
        pipe_logs(child.stderr.take(), "dg-core stderr");

        state.child = Some(child);
        drop(state);

        self.wait_for_ready().await
    }

    pub async fn endpoints(&self) -> Vec<Endpoint> {
        let config = self.config.lock().await;
        let mut endpoints = Vec::new();
        endpoints.push(config.socket_endpoint.clone());
        if let Some(fallback) = &config.tcp_fallback {
            endpoints.push(fallback.clone());
        }
        endpoints
    }

    pub async fn set_allow_network(&self, allow: bool) {
        let mut config = self.config.lock().await;
        config.allow_network = allow;
    }

    pub async fn stop(&self) -> Result<()> {
        let mut state = self.state.lock().await;
        if let Some(mut child) = state.child.take() {
            child.start_kill().ok();
            child.wait().await.ok();
        }
        Ok(())
    }

    pub async fn restart(&self) -> Result<()> {
        self.stop().await?;
        self.ensure_running().await
    }

    pub async fn prepare_runtime(&self, app: &tauri::AppHandle) -> Result<()> {
        let config = self.config.lock().await.clone();
        let resource_dir = app
            .path()
            .resolve("dg_runtime", tauri::path::BaseDirectory::Resource)
            .map_err(|err| anyhow!(err.to_string()))?;

        let version_source = tokio::fs::read_to_string(resource_dir.join("VERSION"))
            .await
            .unwrap_or_default();
        let version_target = tokio::fs::read_to_string(config.runtime_dir.join("VERSION"))
            .await
            .unwrap_or_default();

        let binary_exists = tokio::fs::metadata(&config.binary).await.is_ok();
        if !version_source.is_empty()
            && version_source.trim() == version_target.trim()
            && binary_exists
        {
            return Ok(());
        }

        if tokio::fs::metadata(&config.runtime_dir).await.is_ok() {
            if let Err(err) = tokio::fs::remove_dir_all(&config.runtime_dir).await {
                eprintln!("failed to reset runtime dir {}: {err}", config.runtime_dir.display());
            }
        }

        copy_dir_recursive(&resource_dir, &config.runtime_dir).await?;

        #[cfg(target_family = "unix")]
        {
            use std::os::unix::fs::PermissionsExt;
            if let Ok(metadata) = tokio::fs::metadata(&config.binary).await {
                let mut perms = metadata.permissions();
                perms.set_mode(0o755);
                if let Err(err) = tokio::fs::set_permissions(&config.binary, perms).await {
                    eprintln!("failed to set permissions on {}: {err}", config.binary.display());
                }
            }
        }

        Ok(())
    }


    async fn wait_for_ready(&self) -> Result<()> {
        let endpoints = self.endpoints().await;
        let deadline = Instant::now() + Duration::from_secs(1);

        loop {
            for endpoint in &endpoints {
                if BridgeClient::probe_endpoint(endpoint, Duration::from_millis(200)).await.is_ok() {
                    return Ok(());
                }
            }

            if Instant::now() >= deadline {
                return Err(anyhow!("DG Core did not become ready within timeout"));
            }

            tokio::time::sleep(Duration::from_millis(50)).await;
        }
    }
}

impl Drop for ProcessManager {
    fn drop(&mut self) {
        if let Ok(mut state) = self.state.try_lock() {
            if let Some(mut child) = state.child.take() {
                let _ = child.start_kill();
            }
        }
    }
}

async fn spawn_core(config: &ProcessConfig) -> Result<Child> {
    ensure_dirs(&config.runtime_dir).await?;

    #[cfg(target_family = "unix")]
    if let Endpoint::Unix(path) = &config.socket_endpoint {
        if let Some(parent) = path.parent() {
            if let Err(err) = tokio::fs::create_dir_all(parent).await {
                eprintln!("failed to create ipc directory {}: {err}", parent.display());
            }
        }
        if tokio::fs::metadata(path).await.is_ok() {
            if let Err(err) = tokio::fs::remove_file(path).await {
                eprintln!("failed to remove stale socket {}: {err}", path.display());
            }
        }
    }

    let socket_arg = match &config.socket_endpoint {
        Endpoint::Unix(path) => path.display().to_string(),
        Endpoint::NamedPipe(name) => name.clone(),
        Endpoint::Tcp(addr) => addr.to_string(),
    };

    let mut command = Command::new(&config.binary);
    command
        .arg("serve")
        .arg("--foreground")
        .arg("--socket")
        .arg(&socket_arg)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .current_dir(&config.runtime_dir);

    if config.allow_network {
        command.arg("--allow-network");
    }

    for extra in &config.extra_args {
        command.arg(extra);
    }

    let child = command.spawn().with_context(|| {
        format!(
            "failed to start DG Core using binary '{}'",
            config.binary.display()
        )
    })?;

    Ok(child)
}

fn pipe_logs<R>(stream: Option<R>, label: &'static str)
where
    R: AsyncRead + Unpin + Send + 'static,
{
    if let Some(stream) = stream {
        let mut reader = BufReader::new(stream).lines();
        tokio::spawn(async move {
            while let Ok(Some(line)) = reader.next_line().await {
                println!("[{label}] {line}");
            }
        });
    }
}

async fn ensure_dirs(path: &Path) -> Result<()> {
    tokio::fs::create_dir_all(path)
        .await
        .with_context(|| format!("failed to create runtime directory at {}", path.display()))
}

async fn copy_dir_recursive(src: &Path, dst: &Path) -> Result<()> {
    tokio::fs::create_dir_all(dst).await?;
    let mut entries = tokio::fs::read_dir(src).await?;
    while let Some(entry) = entries.next_entry().await? {
        let entry_path = entry.path();
        let target_path = dst.join(entry.file_name());
        let file_type = entry.file_type().await?;
        if file_type.is_dir() {
            copy_dir_recursive(&entry_path, &target_path).await?;
        } else {
            tokio::fs::copy(&entry_path, &target_path).await?;
        }
    }
    Ok(())
}


