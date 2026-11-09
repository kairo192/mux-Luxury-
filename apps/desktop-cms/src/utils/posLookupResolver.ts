// ============================================================================
// Unified POS lookup: tries the local mirror first, falls back to the live
// API when the mirror misses OR when the mirror simply isn't available
// (browser, mirror not initialised, cold start). The caller gets a single
// shape to work with and a `source` field so the UI can hint at offline mode.
// ============================================================================

import { DesktopCmsApi } from "../api/adminClient";
import { mirrorLookup, isMirrorAvailable } from "./posMirror";

export type LookupSource = "mirror" | "api" | "none";

export interface UnifiedLookupResponse {
  match_type: "variant" | "product" | "search" | "none";
  variant?: any;
  results: any[];
  source: LookupSource;
}

/**
 * The resolver's policy:
 *   1. If the mirror is available AND initialised AND has data → ask it.
 *      If it returns a variant or product match, return immediately.
 *      If it returns match_type=none AND we are online, still try the API
 *      (the mirror may be stale on a brand-new product).
 *   2. Fall back to the API.
 *
 * `preferOnline=true` reverses the order (used for "refresh stock" actions).
 */
export async function resolveLookup(
  term: string,
  opts: { preferOnline?: boolean; online?: boolean } = {},
): Promise<UnifiedLookupResponse> {
  const preferOnline = !!opts.preferOnline;
  const online = opts.online !== false;

  const tryApi = async (): Promise<UnifiedLookupResponse | null> => {
    try {
      const res = await DesktopCmsApi.posLookup(term);
      return {
        match_type: res.match_type,
        variant: res.variant,
        results: res.results ?? [],
        source: "api",
      };
    } catch {
      return null;
    }
  };

  const tryMirror = async (): Promise<UnifiedLookupResponse | null> => {
    if (!isMirrorAvailable()) return null;
    try {
      const m = await mirrorLookup(term);
      if (!m) return null;
      return {
        match_type: m.match_type,
        variant: m.variant,
        results: m.results ?? [],
        source: "mirror",
      };
    } catch {
      return null;
    }
  };

  if (preferOnline && online) {
    const api = await tryApi();
    if (api) return api;
    const mirror = await tryMirror();
    if (mirror) return mirror;
    return { match_type: "none", results: [], source: "none" };
  }

  // Mirror first.
  const mirror = await tryMirror();
  if (mirror && (mirror.match_type === "variant" || mirror.match_type === "product")) {
    return mirror;
  }
  // Mirror missed (or none). If online, try API — it may have fresher data.
  if (online) {
    const api = await tryApi();
    if (api && api.match_type !== "none") return api;
  }
  // Return whatever we have (mirror's "search"/"none" or nothing).
  return mirror ?? { match_type: "none", results: [], source: "none" };
}
