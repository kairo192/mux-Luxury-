// ============================================================================
// MUS LUXURY DESKTOP CMS — AUTO-UPDATE CLIENT
//
// Thin state machine over the Rust commands in src-tauri/src/app_services.rs:
//   updater_status  → is this build configured (public key baked in)?
//   updater_check   → ask the shop server's latest.json (mus-luxury.com/downloads/cms) for a newer version
//   updater_install → download, verify signature, install, restart
//
// Checks run 15 s after start, then every 4 h. A found update raises an
// in-app toast + a Windows notification once per version per session; the
// install itself always waits for the user to click "Installer".
// ============================================================================

import { getTauriInvoke } from "./posHardware";

export type UpdatePhase =
  | "unsupported" // browser / dev server: no native updater
  | "disabled" // desktop build without a signing public key
  | "idle"
  | "checking"
  | "up_to_date"
  | "available"
  | "downloading"
  | "installing"
  | "error";

export interface UpdateState {
  phase: UpdatePhase;
  currentVersion: string | null;
  availableVersion: string | null;
  notes: string | null;
  releaseDate: string | null;
  lastCheckedAt: number | null;
  downloaded: number;
  total: number | null;
  error: string | null;
}

const CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000;
const FIRST_CHECK_DELAY_MS = 15 * 1000;
const PROGRESS_EVENT = "luxe://updater-progress";
export const OPEN_UPDATE_DIALOG_EVENT = "luxe:open-update-dialog";

let state: UpdateState = {
  phase: getTauriInvoke() ? "idle" : "unsupported",
  currentVersion: null,
  availableVersion: null,
  notes: null,
  releaseDate: null,
  lastCheckedAt: null,
  downloaded: 0,
  total: null,
  error: null,
};

type Listener = (s: UpdateState) => void;
const listeners = new Set<Listener>();

function setState(patch: Partial<UpdateState>) {
  state = { ...state, ...patch };
  listeners.forEach((fn) => fn(state));
}

export function getUpdateState(): UpdateState {
  return state;
}

export function subscribeUpdateState(fn: Listener): () => void {
  listeners.add(fn);
  fn(state);
  return () => {
    listeners.delete(fn);
  };
}

export function openUpdateDialog(): void {
  window.dispatchEvent(new CustomEvent(OPEN_UPDATE_DIALOG_EVENT));
}

export async function loadUpdaterStatus(): Promise<UpdateState> {
  const invoke = getTauriInvoke();
  if (!invoke) return state;
  try {
    const s = await invoke("updater_status");
    setState({
      currentVersion: s?.current_version ?? null,
      phase: s?.configured ? (state.phase === "unsupported" || state.phase === "disabled" ? "idle" : state.phase) : "disabled",
    });
  } catch {
    // An older build without the command: behave as "not configured".
    setState({ phase: "disabled" });
  }
  return state;
}

/** Returns the available version, or null. Never throws. */
export async function checkForUpdate(): Promise<string | null> {
  const invoke = getTauriInvoke();
  if (!invoke || state.phase === "disabled" || state.phase === "downloading" || state.phase === "installing") {
    return null;
  }
  setState({ phase: "checking", error: null });
  try {
    const res = await invoke("updater_check");
    if (res?.configured === false) {
      setState({ phase: "disabled", currentVersion: res.current_version ?? state.currentVersion });
      return null;
    }
    if (res?.available) {
      setState({
        phase: "available",
        currentVersion: res.current_version ?? state.currentVersion,
        availableVersion: res.version ?? null,
        notes: res.notes ?? null,
        releaseDate: res.date ?? null,
        lastCheckedAt: Date.now(),
      });
      return res.version ?? null;
    }
    setState({
      phase: "up_to_date",
      currentVersion: res?.current_version ?? state.currentVersion,
      availableVersion: null,
      notes: null,
      lastCheckedAt: Date.now(),
    });
    return null;
  } catch (err: any) {
    setState({ phase: "error", error: String(err?.message || err || "update check failed"), lastCheckedAt: Date.now() });
    return null;
  }
}

/** Downloads + installs the update found by the last check, then the app restarts. */
export async function installUpdate(): Promise<void> {
  const invoke = getTauriInvoke();
  if (!invoke || state.phase !== "available") return;

  let unlisten: (() => void) | null = null;
  try {
    const { listen } = await import("@tauri-apps/api/event");
    unlisten = await listen<any>(PROGRESS_EVENT, (event) => {
      const p = event.payload || {};
      if (p.phase === "installing") {
        setState({ phase: "installing" });
      } else {
        setState({ phase: "downloading", downloaded: Number(p.downloaded || 0), total: p.total ?? null });
      }
    });
  } catch {
    // progress is cosmetic; the install still runs without it
  }

  setState({ phase: "downloading", downloaded: 0, total: null, error: null });
  try {
    await invoke("updater_install");
    // On success the process is replaced/restarted and we never get here.
    setState({ phase: "installing" });
  } catch (err: any) {
    setState({ phase: "error", error: String(err?.message || err || "update install failed") });
  } finally {
    unlisten?.();
  }
}

let schedulerStarted = false;
const announcedVersions = new Set<string>();

/**
 * Starts the background checks. `onNewVersion` is called once per version
 * per session so the UI can raise a toast + Windows notification.
 */
export function startAutoUpdateChecks(onNewVersion: (version: string) => void): () => void {
  if (schedulerStarted || !getTauriInvoke()) return () => {};
  schedulerStarted = true;

  const run = async () => {
    if (state.phase === "disabled") return;
    const version = await checkForUpdate();
    if (version && !announcedVersions.has(version)) {
      announcedVersions.add(version);
      onNewVersion(version);
    }
  };

  let interval: number | undefined;
  const first = window.setTimeout(async () => {
    await loadUpdaterStatus();
    await run();
    interval = window.setInterval(run, CHECK_INTERVAL_MS);
  }, FIRST_CHECK_DELAY_MS);

  return () => {
    window.clearTimeout(first);
    if (interval) window.clearInterval(interval);
    schedulerStarted = false;
  };
}
