use std::path::{Path, PathBuf};

use crate::runtime_paths::runtime_config_dir;
use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

use crate::bridge::TransportKind;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ThemePreference {
    System,
    Light,
    Dark,
}

impl Default for ThemePreference {
    fn default() -> Self {
        Self::System
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct UserSettings {
    pub transport: TransportKind,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub endpoint: Option<String>,
    pub theme: ThemePreference,
    pub allow_network: bool,
}

impl Default for UserSettings {
    fn default() -> Self {
        Self {
            transport: TransportKind::Auto,
            endpoint: None,
            theme: ThemePreference::System,
            allow_network: false,
        }
    }
}

pub struct SettingsStore {
    path: PathBuf,
}

impl SettingsStore {
    pub fn new() -> Result<Self> {
        let runtime_dir = runtime_config_dir().context("unable to resolve runtime directory")?;
        let path = runtime_dir.join("settings.json");
        Ok(Self { path })
    }

    pub async fn load(&self) -> Result<UserSettings> {
        if let Some(parent) = self.path.parent() {
            tokio::fs::create_dir_all(parent).await.ok();
        }

        match tokio::fs::read(&self.path).await {
            Ok(bytes) => {
                let settings = serde_json::from_slice(&bytes).with_context(|| {
                    format!("failed to parse settings at {}", self.path.display())
                })?;
                Ok(settings)
            }
            Err(err) if err.kind() == std::io::ErrorKind::NotFound => Ok(UserSettings::default()),
            Err(err) => Err(err.into()),
        }
    }

    pub async fn save(&self, settings: &UserSettings) -> Result<()> {
        if let Some(parent) = self.path.parent() {
            tokio::fs::create_dir_all(parent).await.with_context(|| {
                format!("failed to prepare settings directory {}", parent.display())
            })?;
        }

        let json = serde_json::to_vec_pretty(settings)?;
        tokio::fs::write(&self.path, json).await?;
        Ok(())
    }

    pub fn path(&self) -> &Path {
        &self.path
    }
}
