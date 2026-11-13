fn main() {
    // The updater public key is baked in with option_env!(); rebuild when it changes.
    println!("cargo:rerun-if-env-changed=LUXE_UPDATER_PUBKEY");
    tauri_build::build()
}
