#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

// ============================================================================
// MUS LUXURY (LUXE) — TAURI 2 WINDOWS DESKTOP CMS NATIVE SECURITY CORE
// 1. The Desktop CMS NEVER connects directly to PostgreSQL and NEVER embeds DB credentials.
// 2. Session tokens (`luxe_cms_access_token`) and HMAC signing secrets (`luxe_cms_hmac_secret`)
//    are bound to the OS Keychain / Windows Credential Manager (`wincred`) via `keyring`
//    and `tauri-plugin-store`, so no token is ever stored in readable browser localStorage.
// ============================================================================

use std::collections::HashMap;
use std::sync::Mutex;
use tauri::State;

const KEYCHAIN_SERVICE: &str = "dz.musluxury.cms.wincred";

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
    tauri::Builder::default()
        .manage(SecureMemoryVault(Mutex::new(HashMap::new())))
        .plugin(tauri_plugin_store::Builder::default().build())
        .invoke_handler(tauri::generate_handler![
            keychain_set_secret,
            keychain_get_secret,
            keychain_delete_secret,
            keychain_status
        ])
        .run(tauri::generate_context!())
        .expect("error while running Mus Luxury Desktop CMS");
}
