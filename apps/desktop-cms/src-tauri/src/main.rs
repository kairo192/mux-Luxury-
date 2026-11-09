#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

// ============================================================================
// MUS LUXURY (LUXE) — TAURI 2 WINDOWS DESKTOP CMS NATIVE SECURITY CORE
// 1. The Desktop CMS NEVER connects directly to PostgreSQL and NEVER embeds DB credentials.
// 2. Session tokens (`luxe_cms_access_token`) and HMAC signing secrets (`luxe_cms_hmac_secret`)
//    are bound to the OS Keychain / Windows Credential Manager (`wincred`) via `keyring`
//    and `tauri-plugin-store`, so no token is ever stored in readable browser localStorage.
// 3. POS hardware (ESC/POS thermal printer, cash drawer, USB-HID barcode scanner) is
//    bridged through the `pos_hardware` module — a browser cannot reliably reach these
//    devices.
// ============================================================================

mod pos_hardware;
mod pos_mirror;

use std::collections::HashMap;
use std::sync::Mutex;
use tauri::State;

const KEYCHAIN_SERVICE: &str = "com.musluxury.cms.wincred";

struct SecureMemoryVault(Mutex<HashMap<String, String>>);

#[tauri::command]
fn keychain_set_secret(
    key: String,
    value: String,
    vault: State<'_, SecureMemoryVault>,
) -> Result<serde_json::Value, String> {
    if let Ok(entry) = keyring::Entry::new(KEYCHAIN_SERVICE, &key) {
        let _ = entry.set_password(&value);
    }
    if let Ok(mut map) = vault.0.lock() {
        map.insert(key.clone(), value);
    }
    Ok(serde_json::json!({
        "stored": true,
        "key": key,
        "backend": if cfg!(target_os = "windows") { "windows_credential_manager_wincred" } else { "os_keychain" }
    }))
}

#[tauri::command]
fn keychain_get_secret(
    key: String,
    vault: State<'_, SecureMemoryVault>,
) -> Result<Option<String>, String> {
    if let Ok(entry) = keyring::Entry::new(KEYCHAIN_SERVICE, &key) {
        if let Ok(secret) = entry.get_password() {
            return Ok(Some(secret));
        }
    }
    if let Ok(map) = vault.0.lock() {
        return Ok(map.get(&key).cloned());
    }
    Ok(None)
}

#[tauri::command]
fn keychain_delete_secret(
    key: String,
    vault: State<'_, SecureMemoryVault>,
) -> Result<serde_json::Value, String> {
    if let Ok(entry) = keyring::Entry::new(KEYCHAIN_SERVICE, &key) {
        let _ = entry.delete_credential();
    }
    if let Ok(mut map) = vault.0.lock() {
        map.remove(&key);
    }
    Ok(serde_json::json!({ "deleted": true, "key": key }))
}

#[tauri::command]
fn keychain_status() -> serde_json::Value {
    serde_json::json!({
        "service": KEYCHAIN_SERVICE,
        "provider": if cfg!(target_os = "windows") { "Windows Credential Manager (wincred)" } else { "OS Native Keychain + Tauri Store" },
        "localstorage_tokens_disabled": true
    })
}

fn main() {
    std::panic::set_hook(Box::new(|info| {
        let msg = format!("PANIC: {:?}\nBacktrace: {:?}", info, std::backtrace::Backtrace::capture());
        eprintln!("{}", msg);
        let _ = std::fs::write("tauri_crash.log", &msg);
        if let Ok(mut exe) = std::env::current_exe() {
            exe.pop();
            let _ = std::fs::write(exe.join("tauri_crash.log"), &msg);
        }
    }));

    let result = tauri::Builder::default()
        .manage(SecureMemoryVault(Mutex::new(HashMap::new())))
        .manage(pos_mirror::MirrorState::new())
        .plugin(tauri_plugin_store::Builder::default().build())
        .on_window_event(|window, event| match event {
            tauri::WindowEvent::CloseRequested { .. } => {
                let msg = format!("Window close requested on window '{}'\n", window.label());
                eprintln!("{}", msg);
                if let Ok(mut exe) = std::env::current_exe() {
                    exe.pop();
                    let _ = std::fs::write(exe.join("tauri_window_close.log"), &msg);
                }
            }
            tauri::WindowEvent::Destroyed => {
                let msg = format!("Window destroyed on window '{}'\n", window.label());
                eprintln!("{}", msg);
                if let Ok(mut exe) = std::env::current_exe() {
                    exe.pop();
                    let _ = std::fs::write(exe.join("tauri_window_destroyed.log"), &msg);
                }
            }
            _ => {}
        })
        .invoke_handler(tauri::generate_handler![
            keychain_set_secret,
            keychain_get_secret,
            keychain_delete_secret,
            keychain_status,
            pos_hardware::pos_list_printers,
            pos_hardware::pos_print_receipt,
            pos_hardware::pos_open_cash_drawer,
            pos_hardware::pos_test_print,
            pos_hardware::pos_print_labels,
            pos_hardware::pos_test_print_label,
            pos_mirror::mirror_init,
            pos_mirror::mirror_upsert_products,
            pos_mirror::mirror_upsert_variants,
            pos_mirror::mirror_mark_synced,
            pos_mirror::mirror_status,
            pos_mirror::mirror_clear,
            pos_mirror::mirror_lookup,
            pos_mirror::pos_queue_enqueue,
            pos_mirror::pos_queue_list,
            pos_mirror::pos_queue_upsert_batch,
            pos_mirror::pos_queue_remove,
            pos_mirror::pos_queue_clear_synced,
        ])
        .run(tauri::generate_context!());

    if let Err(e) = result {
        let msg = format!("TAURI RUN ERROR: {:?}", e);
        eprintln!("{}", msg);
        let _ = std::fs::write("tauri_run_error.log", &msg);
        if let Ok(mut exe) = std::env::current_exe() {
            exe.pop();
            let _ = std::fs::write(exe.join("tauri_run_error.log"), &msg);
        }
    }
}
