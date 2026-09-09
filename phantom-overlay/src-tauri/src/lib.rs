// Tauri backend for Axiom-Grid overlay
// Manages the glassmorphic ghost UI, global shortcuts, and IPC to phantom-core

use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Emitter, Manager, WebviewWindow,
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

#[cfg(windows)]
use window_vibrancy::apply_acrylic;

mod phantom_bridge;
use phantom_bridge::PhantomBridge;

/// IPC command: trigger AI materialization (called from frontend hotkey or button)
#[tauri::command]
async fn trigger_materialize(app: AppHandle, context: String) -> Result<String, String> {
    app.emit("phantom:status", "capturing")
        .map_err(|e| e.to_string())?;

    match PhantomBridge::materialize(context).await {
        Ok(suggestion) => {
            app.emit("phantom:suggestion", &suggestion)
                .map_err(|e| e.to_string())?;
            app.emit("phantom:status", "idle")
                .map_err(|e| e.to_string())?;
            Ok(suggestion)
        }
        Err(e) => {
            app.emit("phantom:status", "error")
                .map_err(|e| e.to_string())?;
            Err(format!("Phantom error: {e}"))
        }
    }
}

/// IPC command: cancel the in-flight materialization, if any
#[tauri::command]
async fn cancel_materialize(app: AppHandle) -> Result<bool, String> {
    let cancelled = PhantomBridge::cancel_active();
    if cancelled {
        app.emit("phantom:status", "cancelled")
            .map_err(|e| e.to_string())?;
    }
    Ok(cancelled)
}

#[tauri::command]
async fn model_readiness() -> Result<phantom_bridge::ReadinessResponse, String> {
    PhantomBridge::readiness().await.map_err(|e| format!("Readiness check failed: {e}"))
}

/// IPC command: toggle overlay visibility
#[tauri::command]
fn toggle_visibility(window: WebviewWindow) {
    if window.is_visible().unwrap_or(false) {
        let _ = window.hide();
    } else {
        let _ = window.show();
        let _ = window.set_focus();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            let _window = app.get_webview_window("main").unwrap();

            // Apply Windows Acrylic/Mica blur behind the overlay
            #[cfg(windows)]
            {
                apply_acrylic(&_window, Some((18, 18, 18, 200)))
                    .expect("Failed to apply acrylic blur");
            }

            // Register global Ctrl+Space hotkey
            let _app_handle = app.handle().clone();
            let shortcut = Shortcut::new(Some(Modifiers::CONTROL), Code::Space);

            app.global_shortcut()
                .on_shortcut(shortcut, move |app, _shortcut, _event| {
                    let window = app.get_webview_window("main").unwrap();

                    if window.is_visible().unwrap_or(false) {
                        // Already visible — trigger materialization
                        let _ = app.emit("phantom:hotkey", ());
                    } else {
                        // Show the overlay
                        let _ = window.show();
                        let _ = app.emit("phantom:hotkey", ());
                    }
                })?;

            // System tray setup
            let quit = MenuItem::with_id(app, "quit", "Quit Axiom-Grid", true, None::<&str>)?;
            let hide = MenuItem::with_id(app, "hide", "Hide / Show", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&hide, &quit])?;

            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("Axiom-Grid — Ctrl+Space to show preview")
                .on_menu_event(move |app, event| match event.id.as_ref() {
                    "quit" => app.exit(0),
                    "hide" => {
                        if let Some(w) = app.get_webview_window("main") {
                            if w.is_visible().unwrap_or(false) {
                                let _ = w.hide();
                            } else {
                                let _ = w.show();
                            }
                        }
                    }
                    _ => {}
                })
                .build(app)?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            trigger_materialize,
            cancel_materialize,
            model_readiness,
            toggle_visibility,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Axiom-Grid overlay");
}
