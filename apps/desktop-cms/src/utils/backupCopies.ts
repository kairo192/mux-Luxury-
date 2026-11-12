// Copies of the server backups on the owner's PC (Documents\Mus Luxury\
// Sauvegardes). The VPS has a 40 GB disk and keeps a limited history; the
// desktop app keeps the newest 60 encrypted copies here. Without the desktop
// app (browser), a copy is a normal file download.
import { DesktopCmsApi } from "../api/adminClient";
import { getTauriInvoke, isTauriRuntime } from "./posHardware";

export type PcCopy = { name: string; size: number; modified: number };
export type PcCopies = { folder: string; items: PcCopy[]; keep: number };

const LAST_COPIED_KEY = "luxe_last_pc_backup_copy";

export function pcCopiesAvailable(): boolean {
  return isTauriRuntime() && getTauriInvoke() !== null;
}

/** Downloads one backup and keeps it on this PC. Returns where it went. */
export async function copyBackupToPc(name: string): Promise<string> {
  const bytes = await DesktopCmsApi.downloadBackupForPc(name);
  const invoke = getTauriInvoke();
  if (invoke && isTauriRuntime()) {
    const res = await invoke("backup_copy_save", { fileName: name, data: Array.from(bytes) });
    localStorage.setItem(LAST_COPIED_KEY, name);
    return String(res?.path || name);
  }
  const url = URL.createObjectURL(new Blob([bytes as Uint8Array<ArrayBuffer>], { type: "application/octet-stream" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  return name;
}

export async function listPcCopies(): Promise<PcCopies | null> {
  const invoke = getTauriInvoke();
  if (!invoke || !isTauriRuntime()) return null;
  return (await invoke("backup_copy_list")) as PcCopies;
}

/** Sends a PC copy (from the copies folder, or a chosen file) back to the server. */
export async function sendPcCopyToServer(source: { name: string } | File): Promise<any> {
  if (source instanceof File) {
    return DesktopCmsApi.importBackupFromPc(source.name, new Uint8Array(await source.arrayBuffer()));
  }
  const invoke = getTauriInvoke();
  if (!invoke) throw new Error("Application de bureau requise.");
  const data: number[] = await invoke("backup_copy_read", { fileName: source.name });
  return DesktopCmsApi.importBackupFromPc(source.name, Uint8Array.from(data));
}

/** Desktop app, owner: keep the newest server backup on this PC (silent;
 *  returns the name copied, or null when already up to date). */
export async function copyNewestBackupIfMissing(): Promise<string | null> {
  if (!pcCopiesAvailable()) return null;
  const status: any = await DesktopCmsApi.getDatabaseStatus();
  const newest = (status?.backups || []).find((b: any) => b.encrypted && String(b.name).endsWith(".enc"));
  if (!newest) return null;
  const local = await listPcCopies();
  if (local?.items.some((c) => c.name === newest.name)) return null;
  await copyBackupToPc(newest.name);
  return newest.name;
}
