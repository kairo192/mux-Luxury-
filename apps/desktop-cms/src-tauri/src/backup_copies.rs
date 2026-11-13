// ============================================================================
// Copies of the server backups on the owner's PC.
//
// The VPS has a 40 GB disk, so it keeps a limited history. The CMS downloads
// the newest backup (still ENCRYPTED with the server's backup key) and stores
// it here: Documents\Mus Luxury\Sauvegardes. The newest 60 copies are kept.
// If the VPS is lost, a copy is sent back from the CMS and restored.
// Only file names produced by the server are accepted (no path traversal).
// ============================================================================

use serde_json::{json, Value};
use std::fs;
use std::path::PathBuf;
use tauri::{AppHandle, Manager};

const KEEP_COPIES: usize = 60;

fn valid_name(name: &str) -> bool {
    name.starts_with("luxe_app_")
        && name.ends_with(".json.gz.enc")
        && name.len() <= 120
        && name
            .chars()
            .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_' || c == '-' || c == '.')
        && !name.contains("..")
}

fn copies_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let docs = app
        .path()
        .document_dir()
        .map_err(|e| format!("Dossier Documents introuvable : {e}"))?;
    let dir = docs.join("Mus Luxury").join("Sauvegardes");
    fs::create_dir_all(&dir).map_err(|e| format!("Impossible de créer {} : {e}", dir.display()))?;
    Ok(dir)
}

fn list_files(dir: &PathBuf) -> Vec<(String, u64, u64)> {
    let mut out = Vec::new();
    if let Ok(entries) = fs::read_dir(dir) {
        for e in entries.flatten() {
            let name = e.file_name().to_string_lossy().to_string();
            if !valid_name(&name) {
                continue;
            }
            if let Ok(meta) = e.metadata() {
                let modified = meta
                    .modified()
                    .ok()
                    .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                    .map(|d| d.as_secs())
                    .unwrap_or(0);
                out.push((name, meta.len(), modified));
            }
        }
    }
    // Newest first (the name carries the date, the file time breaks ties).
    out.sort_by(|a, b| b.0.cmp(&a.0).then(b.2.cmp(&a.2)));
    out
}

#[tauri::command]
pub fn backup_copy_save(app: AppHandle, file_name: String, data: Vec<u8>) -> Result<Value, String> {
    if !valid_name(&file_name) {
        return Err("Nom de sauvegarde refusé.".into());
    }
    if data.len() < 32 || !data.starts_with(b"LUXEBK1\n") {
        return Err("Le fichier reçu n'est pas une sauvegarde chiffrée valide.".into());
    }
    let dir = copies_dir(&app)?;
    let target = dir.join(&file_name);
    let tmp = dir.join(format!("{file_name}.part"));
    fs::write(&tmp, &data).map_err(|e| format!("Écriture impossible : {e}"))?;
    fs::rename(&tmp, &target).map_err(|e| format!("Écriture impossible : {e}"))?;

    let files = list_files(&dir);
    let mut removed = 0;
    for (name, _, _) in files.iter().skip(KEEP_COPIES) {
        if fs::remove_file(dir.join(name)).is_ok() {
            removed += 1;
        }
    }
    Ok(json!({ "path": target.display().to_string(), "folder": dir.display().to_string(), "removed_old": removed }))
}

#[tauri::command]
pub fn backup_copy_list(app: AppHandle) -> Result<Value, String> {
    let dir = copies_dir(&app)?;
    let items: Vec<Value> = list_files(&dir)
        .into_iter()
        .map(|(name, size, modified)| json!({ "name": name, "size": size, "modified": modified }))
        .collect();
    Ok(json!({ "folder": dir.display().to_string(), "items": items, "keep": KEEP_COPIES }))
}

#[tauri::command]
pub fn backup_copy_read(app: AppHandle, file_name: String) -> Result<Vec<u8>, String> {
    if !valid_name(&file_name) {
        return Err("Nom de sauvegarde refusé.".into());
    }
    let path = copies_dir(&app)?.join(&file_name);
    fs::read(&path).map_err(|e| format!("Lecture impossible de {} : {e}", path.display()))
}

#[cfg(test)]
mod tests {
    use super::valid_name;

    #[test]
    fn only_server_backup_names_are_accepted() {
        assert!(valid_name("luxe_app_nightly_20261112_033000_ab12.json.gz.enc"));
        assert!(!valid_name("luxe_app_nightly_20261112.json.gz")); // not encrypted
        assert!(!valid_name("../luxe_app_x.json.gz.enc"));
        assert!(!valid_name("luxe_app_x/../../evil.json.gz.enc"));
        assert!(!valid_name("other.txt"));
    }
}
