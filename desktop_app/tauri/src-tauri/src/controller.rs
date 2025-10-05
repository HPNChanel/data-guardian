use std::path::{Path, PathBuf};
use std::sync::Arc;

use anyhow::{Context, Result};
use base64::{engine::general_purpose, Engine as _};
use dg_core::api::{DGConfig, DataGuardian, EncryptRequest, Envelope};
use serde::{Deserialize, Serialize};
use tokio::fs;
use tokio::sync::broadcast;
use tokio::task;
use tracing::instrument;

const ENCRYPTED_EXTENSION: &str = "dgenc";
const DECRYPTED_EXTENSION: &str = "dg";

#[derive(Debug, Clone)]
pub enum ControllerEvent {
    Progress(String),
    Error(String),
}

#[derive(Clone)]
pub struct Controller {
    dg: Arc<dyn DataGuardian + Send + Sync>,
    events: broadcast::Sender<ControllerEvent>,
}

impl Controller {
    pub fn new(dg: Arc<dyn DataGuardian + Send + Sync>) -> Self {
        let (tx, _rx) = broadcast::channel(64);
        Self { dg, events: tx }
    }

    pub fn subscribe(&self) -> broadcast::Receiver<ControllerEvent> {
        self.events.subscribe()
    }

    async fn emit(&self, event: ControllerEvent) {
        let _ = self.events.send(event);
    }

    #[instrument(skip(self))]
    pub async fn boot(&self, profile: &str, data_dir: PathBuf, telemetry: bool) -> Result<()> {
        let cfg = DGConfig {
            profile: profile.to_owned(),
            data_dir,
            telemetry,
        };
        self.dg
            .init(cfg)
            .await
            .map_err(|err| anyhow::anyhow!("dg init failed: {err}"))
    }

    #[instrument(skip(self))]
    pub async fn encrypt_file(
        &self,
        path: &Path,
        recipients: Vec<String>,
        labels: Vec<String>,
        out_dir: Option<PathBuf>,
    ) -> Result<PathBuf> {
        let canonical = path
            .canonicalize()
            .with_context(|| format!("unable to canonicalize {}", path.display()))?;
        self.guard_policy(
            "local-user",
            "encrypt",
            canonical.to_string_lossy().as_ref(),
        )
        .await?;

        let output_directory = match out_dir {
            Some(dir) => {
                ensure_directory(&dir).await?;
                Some(dir)
            }
            None => None,
        };

        let controller = self.clone();
        let path_buf = canonical.clone();
        let labels_clone = labels.clone();
        let recipients_clone = recipients.clone();
        let output_directory = output_directory.clone();
        let handle = task::spawn(async move {
            controller
                .emit(ControllerEvent::Progress(format!(
                    "encrypting {}",
                    path_buf.display()
                )))
                .await;
            let plaintext = fs::read(&path_buf)
                .await
                .with_context(|| format!("failed to read {}", path_buf.display()))?;
            let envelope = controller
                .dg
                .encrypt(EncryptRequest {
                    plaintext,
                    labels: labels_clone,
                    recipients: recipients_clone,
                })
                .await
                .map_err(|err| anyhow::anyhow!("encryption failed: {err}"))?;
            let target = encrypted_target(&path_buf, output_directory.as_deref())?;
            persist_envelope(&target, &envelope, &path_buf)
                .await
                .with_context(|| format!("failed to write {}", target.display()))?;
            controller
                .emit(ControllerEvent::Progress(format!(
                    "wrote encrypted envelope {}",
                    target.display()
                )))
                .await;
            Ok::<_, anyhow::Error>(target)
        });

        handle.await?
    }

    #[instrument(skip(self))]
    pub async fn decrypt_file(&self, path: &Path, out_dir: Option<PathBuf>) -> Result<PathBuf> {
        let canonical = path
            .canonicalize()
            .with_context(|| format!("unable to canonicalize {}", path.display()))?;
        self.guard_policy(
            "local-user",
            "decrypt",
            canonical.to_string_lossy().as_ref(),
        )
        .await?;

        let output_directory = match out_dir {
            Some(dir) => {
                ensure_directory(&dir).await?;
                Some(dir)
            }
            None => None,
        };

        let controller = self.clone();
        let path_buf = canonical.clone();
        let output_directory_clone = output_directory.clone();
        let handle = task::spawn(async move {
            controller
                .emit(ControllerEvent::Progress(format!(
                    "decrypting {}",
                    path_buf.display()
                )))
                .await;
            let envelope = load_envelope(&path_buf)
                .await
                .with_context(|| format!("unable to load {}", path_buf.display()))?;
            let plaintext = controller
                .dg
                .decrypt(envelope)
                .await
                .map_err(|err| anyhow::anyhow!("decryption failed: {err}"))?;
            let target = decrypted_target(&path_buf, output_directory_clone.as_deref())?;
            fs::write(&target, &plaintext)
                .await
                .with_context(|| format!("failed to write {}", target.display()))?;
            controller
                .emit(ControllerEvent::Progress(format!(
                    "wrote decrypted file {}",
                    target.display()
                )))
                .await;
            Ok::<_, anyhow::Error>(target)
        });

        handle.await?
    }

    #[instrument(skip(self))]
    pub async fn check_access(&self, subject: &str, action: &str, resource: &str) -> Result<bool> {
        self.dg
            .check_policy(subject, action, resource)
            .await
            .map_err(|err| anyhow::anyhow!("policy check failed: {err}"))
    }

    #[instrument(skip(self))]
    pub async fn shutdown(&self) -> Result<()> {
        self.dg
            .shutdown()
            .await
            .map_err(|err| anyhow::anyhow!("shutdown failed: {err}"))
    }

    async fn guard_policy(&self, subject: &str, action: &str, resource: &str) -> Result<()> {
        let allowed = self
            .dg
            .check_policy(subject, action, resource)
            .await
            .map_err(|err| anyhow::anyhow!("policy check failed: {err}"))?;
        if !allowed {
            let message = format!("operation denied by policy for {action} on {resource}");
            self.emit(ControllerEvent::Error(message.clone())).await;
            return Err(anyhow::anyhow!(message));
        }
        Ok(())
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct StoredEnvelope {
    payload: String,
    meta: serde_json::Value,
    original_path: Option<String>,
}

async fn persist_envelope(target: &Path, envelope: &Envelope, source: &Path) -> Result<()> {
    let meta = enrich_meta(envelope, source);
    let encoded = StoredEnvelope {
        payload: general_purpose::STANDARD.encode(&envelope.bytes),
        meta,
        original_path: Some(source.to_string_lossy().into_owned()),
    };
    let serialized = serde_json::to_vec_pretty(&encoded)?;
    fs::write(target, serialized).await?;
    Ok(())
}

async fn load_envelope(path: &Path) -> Result<Envelope> {
    let data = fs::read(path).await?;
    let stored: StoredEnvelope = serde_json::from_slice(&data)?;
    let bytes = general_purpose::STANDARD
        .decode(stored.payload)
        .map_err(|err| anyhow::anyhow!("invalid envelope payload: {err}"))?;
    Ok(Envelope {
        bytes,
        meta: stored.meta,
    })
}

fn enriched_extension(path: &Path, suffix: &str) -> PathBuf {
    let file_name = path
        .file_name()
        .map(|n| n.to_os_string())
        .unwrap_or_else(|| "data".into());
    let mut new_name = file_name;
    new_name.push(".");
    new_name.push(suffix);
    path.with_file_name(new_name)
}

fn encrypted_path(path: &Path) -> PathBuf {
    enriched_extension(path, ENCRYPTED_EXTENSION)
}

fn decrypted_path(path: &Path) -> PathBuf {
    enriched_extension(path, DECRYPTED_EXTENSION)
}

fn enrich_meta(envelope: &Envelope, source: &Path) -> serde_json::Value {
    let mut meta = envelope.meta.clone();
    if let Some(obj) = meta.as_object_mut() {
        obj.insert(
            "source".into(),
            serde_json::Value::String(source.to_string_lossy().into_owned()),
        );
    }
    meta
}

async fn ensure_directory(path: &Path) -> Result<()> {
    let metadata = fs::metadata(path)
        .await
        .with_context(|| format!("output directory does not exist: {}", path.display()))?;
    if !metadata.is_dir() {
        return Err(anyhow::anyhow!(
            "output directory is not a directory: {}",
            path.display()
        ));
    }
    Ok(())
}

fn encrypted_target(path: &Path, out_dir: Option<&Path>) -> Result<PathBuf> {
    if let Some(dir) = out_dir {
        let file_name = encrypted_path(path).file_name().ok_or_else(|| {
            anyhow::anyhow!(
                "unable to determine encrypted file name for {}",
                path.display()
            )
        })?;
        Ok(dir.join(file_name))
    } else {
        Ok(encrypted_path(path))
    }
}

fn decrypted_target(path: &Path, out_dir: Option<&Path>) -> Result<PathBuf> {
    if let Some(dir) = out_dir {
        let file_name = decrypted_path(path).file_name().ok_or_else(|| {
            anyhow::anyhow!(
                "unable to determine decrypted file name for {}",
                path.display()
            )
        })?;
        Ok(dir.join(file_name))
    } else {
        Ok(decrypted_path(path))
    }
}
