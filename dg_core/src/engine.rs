use std::path::Path;
use std::sync::Arc;

use aes_gcm::aead::{Aead, KeyInit};
use aes_gcm::{Aes256Gcm, Nonce};
use rand::rngs::OsRng;
use rand::RngCore;
use tokio::fs;
use tokio::io::AsyncWriteExt;
use tokio::sync::RwLock;
use tracing::{debug, info, instrument, warn};

use crate::api::{DGConfig, DGError, DGResult, DataGuardian, EncryptRequest, Envelope};
use crate::policy::PolicyEngine;

const KEY_FILE: &str = "master.key";
const POLICY_FILE: &str = "policy.json";

#[derive(Clone)]
pub struct DefaultDataGuardian {
    inner: Arc<RwLock<InnerState>>,
}

#[derive(Default)]
struct InnerState {
    config: Option<DGConfig>,
    key: Option<[u8; 32]>,
    policy: Option<PolicyEngine>,
}

impl DefaultDataGuardian {
    pub fn new_arc() -> Arc<dyn DataGuardian + Send + Sync> {
        Arc::new(Self {
            inner: Arc::new(RwLock::new(InnerState::default())),
        })
    }
}

#[async_trait::async_trait]
impl DataGuardian for DefaultDataGuardian {
    #[instrument(skip(self))]
    async fn init(&self, cfg: DGConfig) -> DGResult<()> {
        debug!(profile = %cfg.profile, data_dir = %cfg.data_dir.display(), "initializing Data Guardian");
        fs::create_dir_all(&cfg.data_dir)
            .await
            .map_err(|err| DGError::Config(format!("failed to create data dir: {err}")))?;

        let key = load_or_create_key(&cfg.data_dir).await?;
        let policy = load_policy(&cfg.data_dir).await?;

        let mut guard = self.inner.write().await;
        guard.config = Some(cfg);
        guard.key = Some(key);
        guard.policy = Some(policy);
        info!("Data Guardian initialized");
        Ok(())
    }

    #[instrument(skip(self, req))]
    async fn encrypt(&self, req: EncryptRequest) -> DGResult<Envelope> {
        let guard = self.inner.read().await;
        let (key, config, policy) = guard.parts()?;

        if !policy
            .evaluate("system", "encrypt", "data")
            .await
            .map_err(DGError::Internal)?
        {
            return Err(DGError::PolicyDenied("encryption denied by policy".into()));
        }

        let cipher = Aes256Gcm::new(key.into());
        let mut nonce_bytes = [0u8; 12];
        OsRng.fill_bytes(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);
        let ciphertext = cipher
            .encrypt(nonce, req.plaintext.as_ref())
            .map_err(|err| DGError::Crypto(format!("failed to encrypt: {err}")))?;

        let mut payload = Vec::with_capacity(12 + ciphertext.len());
        payload.extend_from_slice(&nonce_bytes);
        payload.extend_from_slice(&ciphertext);

        let meta = serde_json::json!({
            "labels": req.labels,
            "recipients": req.recipients,
            "profile": config.profile,
        });

        Ok(Envelope {
            bytes: payload,
            meta,
        })
    }

    #[instrument(skip(self, env))]
    async fn decrypt(&self, env: Envelope) -> DGResult<Vec<u8>> {
        let guard = self.inner.read().await;
        let (key, _config, policy) = guard.parts()?;

        if env.bytes.len() < 12 {
            return Err(DGError::Crypto("envelope missing nonce".into()));
        }

        if !policy
            .evaluate("system", "decrypt", "data")
            .await
            .map_err(DGError::Internal)?
        {
            return Err(DGError::PolicyDenied("decryption denied by policy".into()));
        }

        let (nonce, cipher_bytes) = env.bytes.split_at(12);
        let cipher = Aes256Gcm::new(key.into());
        cipher
            .decrypt(Nonce::from_slice(nonce), cipher_bytes)
            .map_err(|err| DGError::Crypto(format!("failed to decrypt: {err}")))
    }

    #[instrument(skip(self))]
    async fn check_policy(&self, subject: &str, action: &str, resource: &str) -> DGResult<bool> {
        let guard = self.inner.read().await;
        let (_, _, policy) = guard.parts()?;
        policy
            .evaluate(subject, action, resource)
            .await
            .map_err(DGError::Internal)
    }

    #[instrument(skip(self))]
    async fn shutdown(&self) -> DGResult<()> {
        let mut guard = self.inner.write().await;
        guard.config = None;
        guard.key = None;
        guard.policy = None;
        info!("Data Guardian shutdown complete");
        Ok(())
    }
}

impl InnerState {
    fn parts(&self) -> DGResult<(&[u8; 32], &DGConfig, &PolicyEngine)> {
        let key = self
            .key
            .as_ref()
            .ok_or_else(|| DGError::Internal("engine not initialized".into()))?;
        let config = self
            .config
            .as_ref()
            .ok_or_else(|| DGError::Internal("config missing".into()))?;
        let policy = self
            .policy
            .as_ref()
            .ok_or_else(|| DGError::Internal("policy not loaded".into()))?;
        Ok((key, config, policy))
    }
}

async fn load_or_create_key(data_dir: &Path) -> DGResult<[u8; 32]> {
    let key_dir = data_dir.join("keys");
    let key_path = key_dir.join(KEY_FILE);
    if let Ok(bytes) = fs::read(&key_path).await {
        if bytes.len() == 32 {
            let mut key = [0u8; 32];
            key.copy_from_slice(&bytes);
            return Ok(key);
        }
        warn!(path = %key_path.display(), "existing key has unexpected length; regenerating");
    }

    fs::create_dir_all(&key_dir)
        .await
        .map_err(|err| DGError::Config(format!("unable to create key directory: {err}")))?;

    let mut key = [0u8; 32];
    OsRng.fill_bytes(&mut key);
    let mut file = fs::File::create(&key_path)
        .await
        .map_err(|err| DGError::Config(format!("unable to create key file: {err}")))?;
    file.write_all(&key)
        .await
        .map_err(|err| DGError::Config(format!("unable to write key file: {err}")))?;
    file.sync_all()
        .await
        .map_err(|err| DGError::Config(format!("unable to flush key file: {err}")))?;
    info!(path = %key_path.display(), "generated new encryption key");
    Ok(key)
}

async fn load_policy(data_dir: &Path) -> DGResult<PolicyEngine> {
    let path = data_dir.join(POLICY_FILE);
    if let Ok(bytes) = fs::read(&path).await {
        return PolicyEngine::from_bytes(bytes)
            .await
            .map_err(|err| DGError::Config(format!("failed to load policy: {err}")));
    }

    PolicyEngine::default()
        .await
        .map_err(|err| DGError::Config(format!("failed to build default policy: {err}")))
}
