// ============================================================================
// useBarcodeScanner — React hook for USB-HID barcode scanners.
//
// Virtually every retail scanner emulates a USB keyboard: it types the code
// at ~1,000 keystrokes per second and ends with Enter. That's indistinguishable
// at the OS level from a human typist, except for the speed. We detect
// scanners by measuring the time between keystrokes: humans type with 50-200 ms
// gaps, scanners stay well under ~30 ms. Anything that accumulates fast enough
// AND ends with a terminator (Enter / Tab) is handled as a scan; everything
// else is left for the normal input field to process.
//
// The hook listens at document level so a scan works no matter which element
// has focus, and will NOT fire inside an <input> or <textarea> (except the
// POS lookup input, which opts in via `data-barcode-target`): that way the
// cashier editing an address never accidentally scans a product into the
// text field.
// ============================================================================
import { useEffect, useRef } from "react";

export interface UseBarcodeScannerOptions {
  /** Minimum code length before a terminator triggers a scan. Default 4. */
  minLength?: number;
  /** Max ms between consecutive keystrokes to still count as the same scan. Default 50. */
  maxIntervalMs?: number;
  /** Keys that mark the end of a scan. Default: Enter and Tab. */
  terminators?: string[];
  /** Pause scanning when `false` (useful to disable during a blocking modal). */
  enabled?: boolean;
}

export function useBarcodeScanner(
  onScan: (code: string) => void,
  opts: UseBarcodeScannerOptions = {},
): void {
  const onScanRef = useRef(onScan);
  onScanRef.current = onScan;

  const {
    minLength = 4,
    maxIntervalMs = 50,
    terminators = ["Enter", "Tab"],
    enabled = true,
  } = opts;

  useEffect(() => {
    if (!enabled) return;

    let buffer = "";
    let lastTs = 0;
    let scanInProgress = false;

    const reset = () => {
      buffer = "";
      lastTs = 0;
      scanInProgress = false;
    };

    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const tag = (target?.tagName || "").toUpperCase();
      const isField = tag === "INPUT" || tag === "TEXTAREA" || target?.isContentEditable;
      const optedIn = target?.dataset?.barcodeTarget === "true";
      // Inside an editable field, only act when the field explicitly opted in.
      if (isField && !optedIn) return;

      const now = Date.now();
      const interval = lastTs ? now - lastTs : 0;

      // Terminator?
      if (terminators.includes(e.key)) {
        if (scanInProgress && buffer.length >= minLength && (interval === 0 || interval <= maxIntervalMs * 3)) {
          const code = buffer;
          e.preventDefault();
          e.stopPropagation();
          reset();
          onScanRef.current(code);
          return;
        }
        reset();
        return;
      }

      // Only printable characters count toward a scan.
      if (e.key.length !== 1) {
        if (scanInProgress) reset();
        return;
      }

      if (!scanInProgress || interval > maxIntervalMs) {
        // New burst — either the first key of a scan, or a fresh human.
        scanInProgress = true;
        buffer = e.key;
        lastTs = now;
        return;
      }

      // Continuation of the same burst.
      buffer += e.key;
      lastTs = now;

      // Guard against runaway buffers (shouldn't ever happen with real scanners).
      if (buffer.length > 128) reset();
    };

    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [enabled, minLength, maxIntervalMs, terminators.join("|")]);
}
