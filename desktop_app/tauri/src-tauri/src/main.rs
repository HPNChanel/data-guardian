use std::path::PathBuf;

use anyhow::Result;
use desktop_app::{
    controller::{Controller, ControllerEvent},
    desktop_config, telemetry,
};
use tauri::Emitter;

#[derive(Clone)]
struct AppState {
    controller: Controller,
    data_dir: PathBuf,
}

#[tauri::command]
async fn encrypt_file(
    state: tauri::State<'_, AppState>,
    path: String,
    recipients: Vec<String>,
    labels: Vec<String>,
) -> Result<String, String> {
    let controller = state.controller.clone();
    let path_buf = PathBuf::from(path);
    controller
        .encrypt_file(&path_buf, recipients, labels)
        .await
        .map(|output| output.to_string_lossy().into_owned())
        .map_err(|err| err.to_string())
}

#[tauri::command]
async fn decrypt_file(state: tauri::State<'_, AppState>, path: String) -> Result<String, String> {
    let controller = state.controller.clone();
    let path_buf = PathBuf::from(path);
    controller
        .decrypt_file(&path_buf)
        .await
        .map(|output| output.to_string_lossy().into_owned())
        .map_err(|err| err.to_string())
}

#[tauri::command]
async fn check_access(
    state: tauri::State<'_, AppState>,
    subject: String,
    action: String,
    resource: String,
) -> Result<bool, String> {
    state
        .controller
        .check_access(&subject, &action, &resource)
        .await
        .map_err(|err| err.to_string())
}

#[tauri::command]
async fn tail_logs(state: tauri::State<'_, AppState>, limit: usize) -> Result<Vec<String>, String> {
    telemetry::tail_logs(&state.data_dir, limit)
        .await
        .map_err(|err| err.to_string())
}

fn configure_updater(builder: tauri::Builder<tauri::Wry>) -> tauri::Builder<tauri::Wry> {
    #[cfg(feature = "auto-update")]
    {
        builder.plugin(tauri_plugin_updater::Builder::new().build())
    }
    #[cfg(not(feature = "auto-update"))]
    {
        builder
    }
}

fn main() {
    if let Err(err) = run_app() {
        eprintln!("Data Guardian desktop failed: {err}");
        std::process::exit(1);
    }
}

fn run_app() -> Result<()> {
    let config = desktop_config::load()?;
    telemetry::init(config.telemetry, &config.data_dir)?;

    let controller = Controller::new(dg_core::api::new_default());
    tauri::async_runtime::block_on(controller.boot(
        &config.profile,
        config.data_dir.clone(),
        config.telemetry,
    ))?;

    let app_state = AppState {
        controller: controller.clone(),
        data_dir: config.data_dir.clone(),
    };

    configure_updater(tauri::Builder::default())
        .manage(app_state.clone())
        .invoke_handler(tauri::generate_handler![
            encrypt_file,
            decrypt_file,
            check_access,
            tail_logs
        ])
        .setup(move |app| {
            let handle = app.handle().clone();
            let mut rx = app_state.controller.subscribe();
            tauri::async_runtime::spawn(async move {
                while let Ok(event) = rx.recv().await {
                    let payload = match event {
                        ControllerEvent::Progress(msg) => serde_json::json!({
                            "kind": "progress",
                            "message": msg,
                        }),
                        ControllerEvent::Error(msg) => serde_json::json!({
                            "kind": "error",
                            "message": msg,
                        }),
                    };
                    let _ = handle.emit("dg://controller", payload);
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())?;

    tauri::async_runtime::block_on(controller.shutdown())?;
    Ok(())
}
