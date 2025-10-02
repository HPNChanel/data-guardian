use std::path::PathBuf;

use anyhow::{Context, Result};
use directories::BaseDirs;

pub fn runtime_config_dir() -> Result<PathBuf> {
    let base_dirs = BaseDirs::new().context("unable to resolve user directories")?;
    let dir = match std::env::consts::OS {
        "macos" => base_dirs.data_dir().join("Data Guardian"),
        "windows" => base_dirs.config_dir().join("Data Guardian"),
        _ => base_dirs.config_dir().join("data-guardian"),
    };
    Ok(dir)
}
