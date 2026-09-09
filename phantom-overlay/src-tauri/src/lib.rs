// Tauri backend for Axiom-Grid overlay
// Explicit preview UI and authenticated IPC to the focused runtime.

use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager, WebviewWindow,
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

mod phantom_bridge;
use phantom_bridge::PhantomBridge;

/// Generate only from explicitly supplied text. No capture or insertion.
#[tauri::command]
async fn trigger_materialize(context: String) -> Result<String, String> {
    PhantomBridge::materialize(context)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn model_readiness() -> Result<phantom_bridge::ReadinessResponse, String> {
    PhantomBridge::readiness().await.map_err(|e| e.to_string())
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
            // A shortcut only shows the review window; it never generates or inserts.
            let shortcut = Shortcut::new(Some(Modifiers::CONTROL), Code::Space);
            // A hotkey conflict must not prevent the ordinary app from starting.
            if app
                .global_shortcut()
                .on_shortcut(shortcut, move |app, _, event| {
                    if event.state == tauri_plugin_global_shortcut::ShortcutState::Pressed {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                        }
                    }
                })
                .is_err()
            {
                eprintln!("Ctrl+Space unavailable; use the application window or tray.");
            }

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
            model_readiness,
            toggle_visibility,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Axiom-Grid overlay");
}
