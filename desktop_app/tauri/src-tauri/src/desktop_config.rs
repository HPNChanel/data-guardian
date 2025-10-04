use std::env;
use std::path::PathBuf;

use anyhow::{anyhow, Context, Result};
use directories::BaseDirs;
use serde::Deserialize;

#[derive(Debug, Clone)]
pub struct DesktopConfig {
    pub profile: String,
    pub telemetry: bool,
    pub data_dir: PathBuf,
}

#[derive(Debug, Deserialize, Default)]
struct FileConfig {
    profile: Option<String>,
    telemetry: Option<bool>,
    data_dir: Option<PathBuf>,
}

pub fn load() -> Result<DesktopConfig> {
    let base = BaseDirs::new().ok_or_else(|| anyhow!("unable to determine base directories"))?;

    let config_path = config_file_path(&base)?;
    let file_cfg = if config_path.exists() {
        let content = std::fs::read_to_string(&config_path)
            .with_context(|| format!("failed to read config file {}", config_path.display()))?;
        toml::from_str::<FileConfig>(&content)
            .with_context(|| format!("invalid config file {}", config_path.display()))?
    } else {
        FileConfig::default()
    };

    let profile = env::var("DG_PROFILE")
        .ok()
        .or(file_cfg.profile)
        .unwrap_or_else(|| "dev".into());
    let telemetry = env::var("DG_TELEMETRY")
        .ok()
        .and_then(|value| value.parse::<bool>().ok())
        .or(file_cfg.telemetry)
        .unwrap_or(false);
    let data_dir = if let Some(dir) = env::var_os("DG_DATA_DIR") {
        PathBuf::from(dir)
    } else if let Some(dir) = file_cfg.data_dir {
        dir
    } else {
        default_data_dir(&base)
    };

    Ok(DesktopConfig {
        profile,
        telemetry,
        data_dir,
    })
}

fn config_file_path(base: &BaseDirs) -> Result<PathBuf> {
    let dir = if cfg!(windows) {
        PathBuf::from(base.config_dir()).join("DataGuardian")
    } else {
        PathBuf::from(base.config_dir()).join("data_guardian")
    };
    std::fs::create_dir_all(&dir)?;
    Ok(dir.join("config.toml"))
}

fn default_data_dir(base: &BaseDirs) -> PathBuf {
    if cfg!(windows) {
        PathBuf::from(base.data_dir()).join("DataGuardian")
    } else {
        PathBuf::from(base.data_dir()).join("data_guardian")
    }
}
