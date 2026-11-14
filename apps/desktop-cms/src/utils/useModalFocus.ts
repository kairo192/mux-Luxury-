import { useEffect, type RefObject } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Open dialogs, bottom to top (ordered by layer, as they are stacked on
// screen): only the topmost one keeps Tab inside itself.
const openDialogs: { el: HTMLElement; layer: number }[] = [];
const topDialog = () => openDialogs[openDialogs.length - 1]?.el;

function focusables(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((n) => n.getClientRects().length > 0);
}

/**
 * Keyboard focus for a modal dialog (the dialog element needs tabIndex={-1}):
 * - on open, focus moves into it (to `initialFocus`, else its first control),
 *   unless something inside already has it;
 * - Tab / Shift+Tab cycle inside the topmost open dialog only;
 * - on close, focus returns to where it was before (the button that opened it),
 *   or to the dialog still open underneath.
 * `layer` follows the visual stacking (a higher z-index → a higher layer): a
 * dialog that opens UNDER another one does not take the focus.
 */
export function useModalFocus(
  dialogRef: RefObject<HTMLElement | null>,
  open: boolean,
  initialFocus?: RefObject<HTMLElement | null>,
  layer = 0,
): void {
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    let at = openDialogs.length;
    while (at > 0 && openDialogs[at - 1].layer > layer) at--;
    openDialogs.splice(at, 0, { el: dialog, layer });
    if (topDialog() === dialog && !dialog.contains(document.activeElement)) {
      (initialFocus?.current || focusables(dialog)[0] || dialog).focus();
    }

    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || topDialog() !== dialog) return;
      const items = focusables(dialog);
      if (items.length === 0) {
        e.preventDefault();
        dialog.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      const outside = !dialog.contains(active);
      if (e.shiftKey && (outside || active === dialog || active === first)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (outside || active === last)) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);

    return () => {
      document.removeEventListener("keydown", onKey, true);
      const wasTop = topDialog() === dialog;
      const i = openDialogs.findIndex((d) => d.el === dialog);
      if (i >= 0) openDialogs.splice(i, 1);
      if (!wasTop) return; // closed underneath another dialog: focus stays up there
      const below = topDialog();
      if (previous && previous.isConnected && (!below || below.contains(previous))) {
        previous.focus();
      } else if (below) {
        (focusables(below)[0] || below).focus();
      }
    };
  }, [open, dialogRef, initialFocus, layer]);
}
