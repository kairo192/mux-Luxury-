// Each area dictionary lists every text once, with its three languages side by
// side: { key: [français, English, العربية] }. Keys are prefixed with the area
// name, so defineArea("pos", { open: [...] }) gives t("pos.open").
export type Triple = readonly [fr: string, en: string, ar: string];
export interface AreaDict { fr: Record<string, string>; en: Record<string, string>; ar: Record<string, string> }

export function defineArea(area: string, entries: Record<string, Triple>): AreaDict {
  const out: AreaDict = { fr: {}, en: {}, ar: {} };
  for (const [k, [fr, en, ar]] of Object.entries(entries)) {
    const key = `${area}.${k}`;
    out.fr[key] = fr;
    out.en[key] = en;
    out.ar[key] = ar;
  }
  return out;
}
