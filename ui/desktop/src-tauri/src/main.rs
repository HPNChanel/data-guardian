#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod bridge;

use bridge::{init_core, manage_state, send_request, subscribe_logs};
use tauri::{Manager, WindowEvent};

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .setup(|app| {
            manage_state(&app.handle());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![init_core, send_request, subscribe_logs])
        .on_window_event(|event| {
            if let WindowEvent::CloseRequested { .. } = event.event() {
                event.window().app_handle().exit(0);
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
