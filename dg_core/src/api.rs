use std::path::PathBuf;
use std::sync::Arc;

use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DGConfig {
    pub profile: String,
    pub data_dir: PathBuf,
    pub telemetry: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EncryptRequest {
    pub plaintext: Vec<u8>,
    pub labels: Vec<String>,
    pub recipients: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Envelope {
    pub bytes: Vec<u8>,
    pub meta: serde_json::Value,
}

#[derive(thiserror::Error, Debug)]
pub enum DGError {
    #[error("policy denied: {0}")]
    PolicyDenied(String),
    #[error("crypto error: {0}")]
    Crypto(String),
    #[error("config error: {0}")]
    Config(String),
    #[error("internal: {0}")]
    Internal(String),
}

pub type DGResult<T> = Result<T, DGError>;

#[async_trait::async_trait]
pub trait DataGuardian {
    async fn init(&self, cfg: DGConfig) -> DGResult<()>;
    async fn encrypt(&self, req: EncryptRequest) -> DGResult<Envelope>;
    async fn decrypt(&self, env: Envelope) -> DGResult<Vec<u8>>;
    async fn check_policy(&self, subject: &str, action: &str, resource: &str) -> DGResult<bool>;
    async fn shutdown(&self) -> DGResult<()>;
}

pub fn new_default() -> Arc<dyn DataGuardian + Send + Sync> {
    crate::engine::DefaultDataGuardian::new_arc()
}
