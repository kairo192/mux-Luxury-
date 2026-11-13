// ============================================================================
// MUS LUXURY — Desktop CMS app services
//
// 1. Native OS notifications (Windows Action Center / toast, macOS Notification
//    Center, libnotify on Linux) for events the cashier must not miss while the
//    CMS window is in the background: new online orders, a ready update,
//    offline-sale sync results.
//
// 2. A crash-safe auto-updater.
//    The previous updater (removed in 500116a) made the app exit at startup
//    when no signing key was configured. Here the updater plugin is only
//    registered when the build was given a public key through the
//    LUXE_UPDATER_PUBKEY environment variable at compile time. Without it
//    every updater command answers `{configured: false}` and nothing else
//    happens — no plugin, no network call, no crash.
//
//    The update files are NOT public: the API serves them only with a valid
//    staff login, so every request carries the CMS session token
//    ("Authorization: Bearer …"). The plugin refuses anything but HTTPS, and
//    installs a file only if its signature matches UPDATER_PUBKEY.
// ============================================================================

use std::sync::Mutex;

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager, State, UserAttentionType};
use tauri_plugin_notification::NotificationExt;
use tauri_plugin_updater::{Update, Updater, UpdaterExt};

/// Public half of the Tauri signing key pair, baked in at compile time.
/// Not a secret: it only lets the app VERIFY that an update was signed by
/// the private key held in the CI secrets.
const UPDATER_PUBKEY: Option<&str> = option_env!("LUXE_UPDATER_PUBKEY");

/// Where the signed release manifest lives. Kept in sync with
/// tauri.conf.json → plugins.updater.endpoints (the plugin reads that one).
const UPDATE_ENDPOINT: &str =
    "https://api.mus-luxury.com/api/v1/admin/updates/cms/latest.json";

const PROGRESS_EVENT: &str = "luxe://updater-progress";

pub fn updater_pubkey() -> Option<&'static str> {
    UPDATER_PUBKEY.map(str::trim).filter(|k| !k.is_empty())
}

/// The update found by the last successful `updater_check`, kept so that
/// `updater_install` installs exactly what the user was shown.
#[derive(Default)]
pub struct PendingUpdate(pub Mutex<Option<Update>>);

fn main_window_is_foreground(app: &AppHandle) -> bool {
    match app.get_webview_window("main") {
        Some(w) => {
            let focused = w.is_focused().unwrap_or(false);
            let minimized = w.is_minimized().unwrap_or(false);
            let visible = w.is_visible().unwrap_or(true);
            focused && visible && !minimized
        }
        None => false,
    }
}

fn clip(text: &str, max: usize) -> String {
    text.chars().take(max).collect()
}

/// Shows a native OS notification.
///
/// With `only_when_unfocused` (the default) nothing is shown while the CMS
/// window is in front, because the in-app toast already covers that case.
/// When shown, the taskbar button also flashes so the cashier notices.
#[tauri::command]
pub fn os_notify(
    app: AppHandle,
    title: String,
    body: String,
    only_when_unfocused: Option<bool>,
) -> Result<Value, String> {
    if only_when_unfocused.unwrap_or(true) && main_window_is_foreground(&app) {
        return Ok(json!({ "shown": false, "reason": "window_focused" }));
    }

    app.notification()
        .builder()
        .title(clip(&title, 120))
        .body(clip(&body, 400))
        .show()
        .map_err(|e| format!("notification failed: {e}"))?;

    if let Some(w) = app.get_webview_window("main") {
        let _ = w.request_user_attention(Some(UserAttentionType::Informational));
    }
    Ok(json!({ "shown": true }))
}

/// Brings the CMS window to the front (used when the user clicks
/// "Voir" on an order toast after coming back from another app).
#[tauri::command]
pub fn app_focus_main_window(app: AppHandle) -> Result<(), String> {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.unminimize();
        let _ = w.show();
        let _ = w.set_focus();
        let _ = w.request_user_attention(None);
    }
    Ok(())
}

#[tauri::command]
pub fn updater_status(app: AppHandle) -> Value {
    json!({
        "configured": updater_pubkey().is_some(),
        "current_version": app.package_info().version.to_string(),
        "endpoint": UPDATE_ENDPOINT,
    })
}

/// An updater whose requests (manifest AND installer download) carry the
/// staff login; the server refuses them otherwise.
fn logged_in_updater(app: &AppHandle, token: &str) -> Result<Updater, String> {
    let token = token.trim();
    if token.is_empty() {
        return Err("connexion requise pour les mises à jour".into());
    }
    app.updater_builder()
        .header("Authorization", format!("Bearer {token}"))
        .map_err(|e| format!("invalid session token: {e}"))?
        .build()
        .map_err(|e| format!("updater unavailable: {e}"))
}

#[tauri::command]
pub async fn updater_check(
    app: AppHandle,
    pending: State<'_, PendingUpdate>,
    token: Option<String>,
) -> Result<Value, String> {
    let current = app.package_info().version.to_string();
    if updater_pubkey().is_none() {
        return Ok(json!({ "configured": false, "available": false, "current_version": current }));
    }
    let Some(token) = token.filter(|t| !t.trim().is_empty()) else {
        // Not logged in: nothing to ask the server yet.
        return Ok(json!({ "configured": true, "available": false, "needs_login": true, "current_version": current }));
    };

    let updater = logged_in_updater(&app, &token)?;
    let found = updater.check().await.map_err(|e| format!("update check failed: {e}"))?;

    let info = match &found {
        Some(u) => json!({
            "configured": true,
            "available": true,
            "current_version": current,
            "version": u.version,
            "notes": u.body,
            "date": u.date.map(|d| d.to_string()),
        }),
        None => json!({ "configured": true, "available": false, "current_version": current }),
    };

    if let Ok(mut slot) = pending.0.lock() {
        *slot = found;
    }
    Ok(info)
}

/// Downloads, verifies (signature against the baked-in public key) and
/// installs the pending update, then restarts the app.
/// Progress is streamed to the UI on `luxe://updater-progress`.
///
/// The check is repeated with the CURRENT login first: the session seen at
/// check time may have expired since, and the download needs a valid one.
/// Only the version the user was shown is installed.
#[tauri::command]
pub async fn updater_install(
    app: AppHandle,
    pending: State<'_, PendingUpdate>,
    token: String,
) -> Result<(), String> {
    if updater_pubkey().is_none() {
        return Err("updater not configured in this build".into());
    }
    let shown = pending
        .0
        .lock()
        .map_err(|_| "updater state poisoned".to_string())?
        .take()
        .ok_or_else(|| "no pending update — check again first".to_string())?;

    let update = logged_in_updater(&app, &token)?
        .check()
        .await
        .map_err(|e| format!("update check failed: {e}"))?
        .ok_or_else(|| "the update is no longer available — check again".to_string())?;
    if update.version != shown.version {
        return Err(format!(
            "a newer version ({}) was published meanwhile — check again",
            update.version
        ));
    }

    let progress_app = app.clone();
    let finished_app = app.clone();
    let mut downloaded: u64 = 0;

    update
        .download_and_install(
            move |chunk, total| {
                downloaded += chunk as u64;
                let _ = progress_app.emit(
                    PROGRESS_EVENT,
                    json!({ "phase": "downloading", "downloaded": downloaded, "total": total }),
                );
            },
            move || {
                let _ = finished_app.emit(PROGRESS_EVENT, json!({ "phase": "installing" }));
            },
        )
        .await
        .map_err(|e| format!("update install failed: {e}"))?;

    // On Windows the NSIS installer has already closed the app and will
    // relaunch it; on macOS / Linux we restart ourselves.
    app.restart();
}
