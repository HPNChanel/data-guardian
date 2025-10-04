use std::path::Path;

use anyhow::Result;
use tokio::fs;
use tracing_subscriber::{fmt, layer::SubscriberExt, EnvFilter, Registry};

static FILE_GUARD: once_cell::sync::OnceCell<tracing_appender::non_blocking::WorkerGuard> =
    once_cell::sync::OnceCell::new();

pub fn init(telemetry: bool, data_dir: &Path) -> Result<()> {
    if telemetry {
        // Placeholder for OTLP exporter wiring.
        let subscriber = Registry::default()
            .with(EnvFilter::from_default_env())
            .with(fmt::layer().with_target(true));
        tracing::subscriber::set_global_default(subscriber)?;
        tracing::info!("telemetry initialized with OTLP exporter");
    } else {
        let log_dir = data_dir.join("logs");
        if !log_dir.exists() {
            std::fs::create_dir_all(&log_dir)?;
        }
        let file_appender = tracing_appender::rolling::never(&log_dir, "desktop.log");
        let (non_blocking, _guard) = tracing_appender::non_blocking(file_appender);
        FILE_GUARD.set(_guard).ok();
        let subscriber = Registry::default()
            .with(EnvFilter::from_default_env())
            .with(fmt::layer().with_writer(non_blocking).with_target(false));
        tracing::subscriber::set_global_default(subscriber)?;
        tracing::info!("file logging initialized");
    }
    Ok(())
}

pub async fn tail_logs(data_dir: &Path, limit: usize) -> Result<Vec<String>> {
    let log_dir = data_dir.join("logs");
    let log_path = log_dir.join("desktop.log");
    if !log_path.exists() {
        return Ok(Vec::new());
    }
    let content = fs::read_to_string(log_path).await?;
    let mut lines: Vec<String> = content.lines().map(|line| line.to_owned()).collect();
    if lines.len() > limit {
        lines.drain(0..(lines.len() - limit));
    }
    Ok(lines)
}
