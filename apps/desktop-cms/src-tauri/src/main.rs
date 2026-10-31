#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

// SECURITY INVARIANT:
// The Desktop CMS NEVER connects directly to PostgreSQL and NEVER embeds DB credentials.
// All administrative operations go through authenticated HTTPS requests to /api/v1/admin/*.

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running Mus Luxury Desktop CMS");
}
