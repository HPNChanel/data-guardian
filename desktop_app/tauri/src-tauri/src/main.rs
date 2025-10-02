use std::sync::Arc;
use std::time::Duration;

use anyhow::{anyhow, Result};
use data_guardian_desktop::bridge::{
    BridgeClient, BridgeConfig, Endpoint, RpcRequest, RpcResponse, TransportKind,
};
use data_guardian_desktop::process::{ProcessConfig, ProcessManager};
use data_guardian_desktop::settings::{SettingsStore, UserSettings};
use tauri::Manager;
use tokio::sync::Mutex;
use uuid::Uuid;

type SharedClient = Arc<Mutex<Option<Arc<BridgeClient>>>>;

#[cfg(feature = "auto-update")]
fn configure_updater(builder: tauri::Builder<tauri::Wry>) -> tauri::Builder<tauri::Wry> {
    let _ = tauri::updater::builder();
    builder
}

#[cfg(not(feature = "auto-update"))]
fn configure_updater(builder: tauri::Builder<tauri::Wry>) -> tauri::Builder<tauri::Wry> {
    builder
}

#[tauri::command]
async fn dg_rpc(
    state: tauri::State<'_, AppState>,
    method: String,
    params: Option<serde_json::Value>,
    timeout_ms: Option<u64>,
) -> Result<RpcResponse, String> {
    let client = state
        .ensure_client(timeout_ms)
        .await
        .map_err(|err| format!("bridge error: {err}"))?;

    let request = RpcRequest {
        id: Uuid::new_v4().to_string(),
        method,
        params,
    };

    client
        .send_request(request)
        .await
        .map_err(|err| format!("rpc dispatch failed: {err}"))
}

#[tauri::command]
async fn load_settings(state: tauri::State<'_, AppState>) -> Result<UserSettings, String> {
    let settings = state.settings.lock().await.clone();
    Ok(settings)
}

#[tauri::command]
async fn save_settings(
    state: tauri::State<'_, AppState>,
    updated: UserSettings,
) -> Result<(), String> {
    let previous_allow = {
        let mut guard = state.settings.lock().await;
        let previous = guard.allow_network;
        *guard = updated.clone();
        previous
    };

    state
        .settings_store
        .save(&updated)
        .await
        .map_err(|err| err.to_string())?;

    state.process.set_allow_network(updated.allow_network).await;

    if previous_allow != updated.allow_network {
        state
            .process
            .restart()
            .await
            .map_err(|err| err.to_string())?;
    } else {
        state
            .process
            .ensure_running()
            .await
            .map_err(|err| err.to_string())?;
    }

    let mut client = state.client.lock().await;
    *client = None;

    Ok(())
}

#[tauri::command]
async fn dg_check_updates(app: tauri::AppHandle) -> Result<String, String> {
    match tauri::updater::check(&app).await {
        Ok(Some(update)) => {
            let mut message = format!("Update {} available", update.version);
            if let Some(body) = update.body {
                message.push_str(": ");
                message.push_str(body.trim());
            }
            Ok(message)
        }
        Ok(None) => Ok("You are running the latest version.".into()),
        Err(err) => Err(err.to_string()),
    }
}

#[derive(Clone)]
struct AppState {
    client: SharedClient,
    settings: Arc<Mutex<UserSettings>>,
    settings_store: Arc<SettingsStore>,
    process: Arc<ProcessManager>,
}

impl AppState {
    async fn ensure_client(&self, timeout_override: Option<u64>) -> Result<Arc<BridgeClient>> {
        let cached = {
            let guard = self.client.lock().await;
            guard.clone()
        };

        if let Some(client) = cached {
            return Ok(client);
        }

        self.process.ensure_running().await?;
        let config = self.build_client_config(timeout_override).await?;
        let client = Arc::new(BridgeClient::connect(config).await?);

        let mut guard = self.client.lock().await;
        *guard = Some(client.clone());
        Ok(client)
    }

    async fn build_client_config(&self, timeout_override: Option<u64>) -> Result<BridgeConfig> {
        let settings = self.settings.lock().await.clone();
        let mut endpoints = Vec::new();

        if settings.transport != TransportKind::Auto {
            if let Some(value) = settings.endpoint.as_deref() {
                match Endpoint::from_user_input(settings.transport, value) {
                    Ok(endpoint) => endpoints.push(endpoint),
                    Err(err) => {
                        eprintln!("invalid custom endpoint '{value}': {err}");
                    }
                }
            }
        }

        let defaults = self.process.endpoints().await;
        for endpoint in defaults {
            if settings.transport != TransportKind::Auto
                && endpoint.kind() == settings.transport
                && !endpoints.contains(&endpoint)
            {
                endpoints.insert(0, endpoint.clone());
                continue;
            }

            if !endpoints.contains(&endpoint) {
                endpoints.push(endpoint);
            }
        }

        if endpoints.is_empty() {
            return Err(anyhow!("no available endpoints configured"));
        }

        let timeout = Duration::from_millis(timeout_override.unwrap_or(5_000));

        Ok(BridgeConfig::new(endpoints)
            .with_timeout(timeout)
            .with_retries(2))
    }
}

#[tauri::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let settings_store = Arc::new(SettingsStore::new()?);
    let settings = settings_store.load().await.unwrap_or_default();

    let process_manager = Arc::new(ProcessManager::new(ProcessConfig::default()));
    process_manager
        .set_allow_network(settings.allow_network)
        .await;

    let app_state = AppState {
        client: Arc::new(Mutex::new(None)),
        settings: Arc::new(Mutex::new(settings)),
        settings_store,
        process: process_manager.clone(),
    };

    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_store::Builder::default().build());
    let builder = configure_updater(builder);

    builder
        .setup(move |app| {
            let state = app_state.clone();
            app.manage(state.clone());

            let handle = app.handle();
            let process = state.process.clone();
            tauri::async_runtime::spawn(async move {
                if let Err(err) = process.prepare_runtime(&handle).await {
                    handle
                        .emit(
                            "dg-core:error",
                            format!("runtime preparation failed: {err}"),
                        )
                        .unwrap_or_else(|emit_err| {
                            eprintln!("failed to emit core error event: {emit_err}");
                        });
                    return;
                }

                if let Err(err) = process.ensure_running().await {
                    handle
                        .emit("dg-core:error", err.to_string())
                        .unwrap_or_else(|emit_err| {
                            eprintln!("failed to emit core error event: {emit_err}");
                        });
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            dg_rpc,
            load_settings,
            save_settings,
            dg_check_updates
        ])
        .run(tauri::generate_context!())
        .await?;

    Ok(())
}
