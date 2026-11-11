// Opens an https:// link outside the CMS window: in the desktop app through
// the Rust command `open_external_url` (default browser / WhatsApp Desktop),
// in a browser through a new tab.
import { getTauriInvoke } from "./posHardware";

export async function openExternalUrl(url: string): Promise<void> {
  if (!/^https:\/\/\S+$/.test(url)) throw new Error("Lien invalide");
  const invoke = getTauriInvoke();
  if (invoke) {
    await invoke("open_external_url", { url });
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}
