// ============================================================================
// WINDOWS CREDENTIAL MANAGER (wincred) / TAURI 2 OS KEYCHAIN BRIDGE
// Binds sensitive session tokens and HMAC signing keys to the OS Keychain
// via Tauri IPC (`keychain_set_secret`, `keychain_get_secret`, `keychain_delete_secret`).
// Strictly avoids storing any authentication token or secret in browser localStorage.
// ============================================================================

const volatileMemorySecrets: Record<string, string> = {};

function getTauriInvoke(): ((cmd: string, args?: Record<string, unknown>) => Promise<any>) | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  if (w.__TAURI_INTERNALS__ && typeof w.__TAURI_INTERNALS__.invoke === "function") {
    return w.__TAURI_INTERNALS__.invoke.bind(w.__TAURI_INTERNALS__);
  }
  if (w.__TAURI__ && w.__TAURI__.core && typeof w.__TAURI__.core.invoke === "function") {
    return w.__TAURI__.core.invoke.bind(w.__TAURI__.core);
  }
  return null;
}

export async function keychainSetSecret(key: string, value: string): Promise<void> {
  volatileMemorySecrets[key] = value;
  const invoke = getTauriInvoke();
  if (invoke) {
    try {
      await invoke("keychain_set_secret", { key, value });
    } catch {
      // Fallback remains in volatile process memory only (never written to localStorage)
    }
  }
}

export async function keychainGetSecret(key: string): Promise<string | null> {
  if (volatileMemorySecrets[key]) {
    return volatileMemorySecrets[key];
  }
  const invoke = getTauriInvoke();
  if (invoke) {
    try {
      const val = await invoke("keychain_get_secret", { key });
      if (typeof val === "string" && val.length > 0) {
        volatileMemorySecrets[key] = val;
        return val;
      }
    } catch {
      return null;
    }
  }
  return null;
}

export async function keychainDeleteSecret(key: string): Promise<void> {
  delete volatileMemorySecrets[key];
  const invoke = getTauriInvoke();
  if (invoke) {
    try {
      await invoke("keychain_delete_secret", { key });
    } catch {
      // Ignore
    }
  }
}

export async function getOsKeychainStatus(): Promise<{
  service: string;
  provider: string;
  localstorage_tokens_disabled: boolean;
  /** true only when the Windows/macOS credential vault really answered. */
  os_keychain: boolean;
}> {
  const invoke = getTauriInvoke();
  if (invoke) {
    try {
      const res: any = await invoke("keychain_status");
      return { ...res, os_keychain: true };
    } catch {
      // fall through: report honestly that the vault is not available
    }
  }
  return {
    service: "dz.musluxury.cms.secure",
    provider: "Session du navigateur (sans coffre-fort système)",
    localstorage_tokens_disabled: true,
    os_keychain: false,
  };
}
