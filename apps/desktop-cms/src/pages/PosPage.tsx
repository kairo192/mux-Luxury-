import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  ScanLine,
  Search,
  Plus,
  Minus,
  Trash2,
  ShoppingCart,
  Lock,
  Unlock,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Printer,
  RotateCcw,
  X,
  History,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { notifyClient } from "../utils/clientNotifier";
import { useT } from "../i18n";
import {
  subscribePosQueue,
  enqueuePosSale,
  syncPosQueue,
  removeSyncedItems,
  getPosQueue,
  type PosQueueItem,
} from "../utils/posOfflineQueue";
import { InvoiceModal } from "../components/InvoiceModal";
import { PrinterSettingsModal } from "../components/PrinterSettingsModal";
import { BarcodeLabelModal } from "../components/BarcodeLabelModal";
import { FileText as FileTextIcon, Settings as SettingsIcon, Tag as TagIcon } from "lucide-react";
import { Wifi, WifiOff, CloudUpload, CloudOff, User, UserCheck } from "lucide-react";
import {
  isHardwareConfigured,
  printSaleReceipt,
  loadHardwareSettings,
  openCashDrawer as kickDrawer,
} from "../utils/posHardware";
import { useBarcodeScanner } from "../utils/useBarcodeScanner";
import { openSystemPrint, renderReceiptHtml } from "../utils/systemPrint";
import { resolveLookup } from "../utils/posLookupResolver";
import { syncCatalog, ensureMirrorReady } from "../utils/posMirrorSync";
import { mirrorStatus, type MirrorStatus as MirrorStatusType } from "../utils/posMirror";
import type { CartLine, LookupVariant, PaymentMethod, RegisterSession } from "./pos/types";
import { Keypad, ReceiptModal, Stat, fmt } from "./pos/ui";
import { buildReceiptBlocks } from "./pos/receipt";
import { CloseRegisterSheet, ConflictsSheet, CustomerSheet, PaymentSheet, RefundSheet, SessionsHistorySheet, VariantPickerSheet } from "./pos/sheets";

// ---------------------------------------------------------------------------
// POS — Touch-first cashier workspace.
// Design tuned for a digital (touchscreen) register per Apple HIG:
//   · Targets >= 48px  (accessibility.md > Interactions: iOS/iPadOS 44x44pt)
//   · Base type 14-16px, totals 24-30px (accessibility.md > Legibility: 17pt default)
//   · Emerald/gold brand kept as the signature; gold reserved for the one
//     primary action (Encaisser). (branding.md: brand color for primary actions)
//   · On-screen numeric keypad for cash entry (no physical keyboard on a till).
// ---------------------------------------------------------------------------


export const PosPage: React.FC<{ onInventoryUpdated?: () => void }> = ({ onInventoryUpdated }) => {
  const t = useT();
  const [session, setSession] = useState<RegisterSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [openingFloat, setOpeningFloat] = useState("0");
  const [countedCash, setCountedCash] = useState("0");
  const [showClose, setShowClose] = useState(false);
  const [busy, setBusy] = useState(false);

  const [scanCode, setScanCode] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [variantPicker, setVariantPicker] = useState<any | null>(null);
  const scanRef = useRef<HTMLInputElement>(null);

  const [cart, setCart] = useState<CartLine[]>([]);
  const [orderDiscount, setOrderDiscount] = useState("");
  const [payMethod, setPayMethod] = useState<PaymentMethod>("cash");
  const [tendered, setTendered] = useState("0");
  const [showPay, setShowPay] = useState(false);

  const [receipt, setReceipt] = useState<any | null>(null);
  const [recentSales, setRecentSales] = useState<any[]>([]);
  const [refundTarget, setRefundTarget] = useState<any | null>(null);
  const [sessionsHistory, setSessionsHistory] = useState<any[] | null>(null);
  const [invoiceSaleId, setInvoiceSaleId] = useState<number | null>(null);

  // Customer attach
  const [customer, setCustomer] = useState<{ id: number; full_name: string; phone: string } | null>(null);
  const [showCustomer, setShowCustomer] = useState(false);
  const [custQuery, setCustQuery] = useState("");
  const [custResults, setCustResults] = useState<any[]>([]);
  const [custNewName, setCustNewName] = useState("");
  const [custNewPhone, setCustNewPhone] = useState("");

  // Offline-first state
  const [online, setOnline] = useState<boolean>(typeof navigator !== "undefined" ? navigator.onLine !== false : true);
  const [queue, setQueue] = useState<PosQueueItem[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [showConflicts, setShowConflicts] = useState(false);
  const [showPrinterSettings, setShowPrinterSettings] = useState(false);
  const [labelVariantId, setLabelVariantId] = useState<number | null>(null);
  const [mirrorStat, setMirrorStat] = useState<MirrorStatusType | null>(null);
  const [mirrorSyncing, setMirrorSyncing] = useState(false);
  const [lastLookupSource, setLastLookupSource] = useState<"mirror" | "api" | "none">("none");
  const queueCounts = {
    pending: queue.filter((i) => i.status === "pending").length,
    conflict: queue.filter((i) => i.status === "conflict").length,
    failed: queue.filter((i) => i.status === "failed").length,
  };

  const loadRegister = useCallback(async () => {
    try {
      const data = await DesktopCmsApi.posRegisterCurrent();
      setSession(data.open ? data.session : null);
    } catch (e: any) {
      setError(e?.userMessage || "Impossible de charger la caisse");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadRecentSales = useCallback(async () => {
    try {
      const data = await DesktopCmsApi.posListSales(15);
      setRecentSales(data.items || []);
    } catch {
      /* non-fatal */
    }
  }, []);

  useEffect(() => {
    loadRegister();
    loadRecentSales();
  }, [loadRegister, loadRecentSales]);

  useEffect(() => {
    if (session && scanRef.current) scanRef.current.focus();
  }, [session]);

  const flashSuccess = (msg: string) => {
    setSuccess(msg);
    setError(null);
    setTimeout(() => setSuccess(null), 4000);
  };
  const flashError = (msg: string) => {
    setError(msg);
    setTimeout(() => setError(null), 6000);
  };

  // ------------------------------------------------------------ offline sync
  const runSync = useCallback(async (silent = false) => {
    if (getPosQueue().filter((i) => i.status === "pending" || i.status === "failed").length === 0) return;
    setSyncing(true);
    try {
      const summary = await syncPosQueue((ops) => DesktopCmsApi.posSync(ops) as any);
      if (summary) {
        removeSyncedItems();
        if (!silent) {
          const parts: string[] = [];
          if (summary.created) parts.push(`${summary.created} synchronisée(s)`);
          if (summary.duplicate) parts.push(`${summary.duplicate} déjà connue(s)`);
          if (summary.conflict) parts.push(`${summary.conflict} conflit(s)`);
          flashSuccess(`Synchronisation : ${parts.join(", ") || "rien à faire"}`);
        } else {
          // Background sync (reconnect / app start): the cashier may be in
          // another tab or app, so surface the result in the notification
          // center and, when the CMS is in background, as a Windows alert.
          if (summary.created) {
            notifyClient({
              type: "success",
              category: "sync",
              os: true,
              showModalBox: false,
              title: t("sync.bg_title"),
              message: t("sync.bg_body", { n: summary.created }),
            });
          }
          if (summary.conflict) {
            notifyClient({
              type: "warning",
              category: "sync",
              os: true,
              showModalBox: false,
              durationMs: 0,
              title: t("sync.conflict_title"),
              message: t("sync.conflict_body", { n: summary.conflict }),
            });
          }
        }
        loadRegister();
        loadRecentSales();
        onInventoryUpdated?.();
      }
    } finally {
      setSyncing(false);
    }
  }, [loadRegister, loadRecentSales, onInventoryUpdated, t]);

  useEffect(() => {
    const unsub = subscribePosQueue(setQueue);
    const goOnline = () => {
      setOnline(true);
      runSync(true);
    };
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    // Attempt a sync on mount in case sales are pending from a previous run.
    runSync(true);
    return () => {
      unsub();
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, [runSync]);

  const isNetworkError = (e: any) => !navigator.onLine || e?.status === 0 || e?.code === "NETWORK_ERROR" || e?.status === undefined;

  // ------------------------------------------------------------ register
  const handleOpenRegister = async () => {
    const amount = parseInt(openingFloat || "0", 10);
    if (isNaN(amount) || amount < 0) return flashError("Fond de caisse invalide");
    setBusy(true);
    try {
      const s = await DesktopCmsApi.posRegisterOpen(amount, "Caisse principale");
      setSession(s);
      setOpeningFloat("0");
      flashSuccess(`Caisse ouverte avec un fond de ${fmt(amount)}`);
    } catch (e: any) {
      flashError(e?.userMessage || "Ouverture de caisse refusée");
    } finally {
      setBusy(false);
    }
  };

  const handleCloseRegister = async () => {
    const amount = parseInt(countedCash || "0", 10);
    if (isNaN(amount) || amount < 0) return flashError("Montant compté invalide");
    setBusy(true);
    try {
      const closed = await DesktopCmsApi.posRegisterClose(amount);
      const variance = closed.variance_dzd;
      setSession(null);
      setShowClose(false);
      setCountedCash("0");
      flashSuccess(
        `Caisse clôturée. Attendu ${fmt(closed.expected_cash_dzd)}, compté ${fmt(closed.counted_cash_dzd)}, écart ${variance >= 0 ? "+" : ""}${fmt(variance)}`
      );
    } catch (e: any) {
      flashError(e?.userMessage || "Clôture refusée");
    } finally {
      setBusy(false);
    }
  };

  // ------------------------------------------------------------ scanning
  const addVariantToCart = (v: LookupVariant) => {
    setCart((prev) => {
      const existing = prev.find((l) => l.variant_id === v.variant_id);
      if (existing) {
        if (existing.quantity + 1 > v.stock_qty) {
          flashError(`Stock insuffisant pour ${v.product_name} (${v.variant_title}): ${v.stock_qty} dispo`);
          return prev;
        }
        return prev.map((l) => (l.variant_id === v.variant_id ? { ...l, quantity: l.quantity + 1 } : l));
      }
      if (v.stock_qty < 1) {
        flashError(`${v.product_name} (${v.variant_title}) en rupture de stock`);
        return prev;
      }
      return [
        ...prev,
        {
          variant_id: v.variant_id,
          product_id: v.product_id,
          product_name: v.product_name,
          variant_title: v.variant_title,
          sku: v.sku,
          unit_price_dzd: v.unit_price_dzd,
          quantity: 1,
          line_discount_dzd: 0,
          stock_qty: v.stock_qty,
        },
      ];
    });
    setSearchResults([]);
    setVariantPicker(null);
    setScanCode("");
    scanRef.current?.focus();
  };

  // Manual (Enter / Chercher) lookup. Goes through resolveLookup which
  // tries the local mirror first and falls back to the API — so the POS
  // keeps working even on a dead connection.
  const handleScan = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const code = scanCode.trim();
    if (!code) return;
    try {
      const res = await resolveLookup(code, { online });
      setLastLookupSource(res.source);
      if (res.match_type === "variant") {
        addVariantToCart(res.variant);
        setSearchResults([]);
        setScanCode("");
      } else if (res.match_type === "product") {
        setVariantPicker(res.results[0]);
      } else if (res.match_type === "search" && res.results.length) {
        setSearchResults(res.results);
      } else {
        flashError(`Aucun produit pour « ${code} »`);
      }
    } catch (e: any) {
      flashError(e?.userMessage || "Recherche échouée");
    }
  };

  // Live incremental search — luxury items (bags, pieces) rarely have a
  // barcode, so the cashier types part of the product name and the matching
  // products appear below without having to press Enter. Only fires for
  // human-speed typing (debounced) so a USB scanner's fast burst still falls
  // through to the scanner hook / handleScan path and doesn't double-call.
  useEffect(() => {
    const term = scanCode.trim();
    // Short queries would flood the API with too many results; two chars min
    // is also what the operator would type intentionally.
    if (term.length < 2) {
      setSearchResults([]);
      return;
    }
    const handle = setTimeout(async () => {
      try {
        const res = await resolveLookup(term, { online });
        setLastLookupSource(res.source);
        if (res.match_type === "search" || res.match_type === "product") {
          setSearchResults(res.results);
        } else if (res.match_type === "variant" && res.variant) {
          // Exact code match while still typing — don't auto-add from live
          // search; keep the exact match available if the operator presses
          // Enter. (The scanner hook's path handles instant adds.)
          setSearchResults([{
            id: res.variant.product_id,
            name_fr: res.variant.product_name,
            selling_price_dzd: res.variant.unit_price_dzd,
            main_image_url: res.variant.main_image_url,
            variants: [res.variant],
          }]);
        } else {
          setSearchResults([]);
        }
      } catch {
        // Silent on live search — the explicit submit will surface errors.
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [scanCode, online]);

  // ------------------------------------------------------------ cart math
  const updateQty = (variantId: number, delta: number) => {
    setCart((prev) =>
      prev.flatMap((l) => {
        if (l.variant_id !== variantId) return [l];
        const q = l.quantity + delta;
        if (q <= 0) return [];
        if (q > l.stock_qty) {
          flashError(`Stock maximum ${l.stock_qty} atteint pour ${l.product_name}`);
          return [l];
        }
        return [{ ...l, quantity: q }];
      })
    );
  };

  const removeLine = (variantId: number) => setCart((prev) => prev.filter((l) => l.variant_id !== variantId));

  const subtotal = cart.reduce((s, l) => s + l.unit_price_dzd * l.quantity, 0);
  const lineDiscounts = cart.reduce((s, l) => s + Math.min(l.line_discount_dzd, l.unit_price_dzd * l.quantity), 0);
  const orderDisc = Math.min(parseInt(orderDiscount || "0", 10) || 0, subtotal - lineDiscounts);
  const total = subtotal - lineDiscounts - orderDisc;
  const itemCount = cart.reduce((s, l) => s + l.quantity, 0);
  // Empty = the customer pays the exact amount. The amount received is never
  // pre-filled, so a discount applied afterwards cannot leave a stale figure.
  const tenderedNum = parseInt(tendered || "0", 10) || 0;
  const receivedShown = tenderedNum > 0 ? tenderedNum : total;
  const change = payMethod === "cash" ? Math.max(0, tenderedNum - total) : 0;

  const clearCart = () => {
    setCart([]);
    setOrderDiscount("");
    setTendered("0");
    setPayMethod("cash");
    setCustomer(null);
  };

  // ------------------------------------------------------------ customer
  const searchCustomer = async () => {
    const q = custQuery.trim();
    if (!q) return;
    try {
      const d = await DesktopCmsApi.searchCustomers(q);
      setCustResults(d.items || []);
    } catch (e: any) {
      flashError(e?.userMessage || "Recherche client échouée");
    }
  };

  const pickCustomer = (c: any) => {
    setCustomer({ id: c.id, full_name: c.full_name, phone: c.phone });
    setShowCustomer(false);
    setCustQuery("");
    setCustResults([]);
  };

  const createCustomer = async () => {
    if (custNewName.trim().length < 2 || custNewPhone.trim().length < 6) {
      return flashError("Nom et téléphone requis");
    }
    try {
      const c = await DesktopCmsApi.createCustomer({ full_name: custNewName.trim(), phone: custNewPhone.trim() });
      setCustomer({ id: c.id, full_name: c.full_name, phone: c.phone });
      setShowCustomer(false);
      setCustNewName("");
      setCustNewPhone("");
      flashSuccess(`Client ${c.full_name} rattaché`);
    } catch (e: any) {
      flashError(e?.userMessage || "Création client refusée");
    }
  };

  // ------------------------------------------------------------ checkout
  const handleConfirmSale = async () => {
    // (tendered empty = exact amount)
    if (!cart.length) return flashError("Panier vide");
    if (total <= 0) return flashError("Total invalide");
    if (payMethod === "cash" && tenderedNum > 0 && tenderedNum < total) {
      return flashError("Montant reçu inférieur au total");
    }
    setBusy(true);
    const idemKey = `pos-sale-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const payload = {
      items: cart.map((l) => ({ variant_id: l.variant_id, quantity: l.quantity, line_discount_dzd: l.line_discount_dzd || 0 })),
      payments: [
        {
          method: payMethod,
          amount_dzd: total,
          tendered_dzd: payMethod === "cash" && tenderedNum > 0 ? tenderedNum : undefined,
        },
      ],
      order_discount_dzd: orderDisc,
      customer_id: customer?.id ?? null,
    };
    try {
      const sale = await DesktopCmsApi.posCreateSale(payload, idemKey);
      setReceipt(sale);
      clearCart();
      setShowPay(false);
      flashSuccess(`Vente ${sale.sale_reference} enregistrée — ${fmt(sale.total_dzd)}`);
      loadRegister();
      loadRecentSales();
      onInventoryUpdated?.();
      // Fire-and-forget: print on the thermal printer + kick the drawer if the
      // sale included cash. Errors are shown but never block the sale itself.
      if (isHardwareConfigured()) {
        printSaleReceipt(sale as any).then((r) => {
          if (!r.ok) flashError(`Imprimante : ${r.error}`);
        }).catch(() => { /* fire-and-forget */ });
      } else if (payMethod === "cash") {
        // Printer not set up — still try to kick the drawer so cash can be put in.
        // Only if the Tauri runtime / a device path is available at all.
        kickDrawer(loadHardwareSettings()).then(() => {}).catch(() => {});
      }
    } catch (e: any) {
      if (isNetworkError(e)) {
        // Offline: never lose the sale. Queue it durably for later idempotent sync.
        const item = enqueuePosSale(payload, total, session?.id ?? null);
        setReceipt({
          offline: true,
          sale_reference: item.client_txn_id,
          created_at: item.created_at,
          sale_type: "sale",
          subtotal_dzd: subtotal,
          discount_dzd: lineDiscounts + orderDisc,
          tax_dzd: 0,
          total_dzd: total,
          items: cart.map((l) => ({
            id: l.variant_id,
            quantity: l.quantity,
            product_name: l.product_name,
            variant_title: l.variant_title,
            line_total_dzd: l.unit_price_dzd * l.quantity - Math.min(l.line_discount_dzd, l.unit_price_dzd * l.quantity),
          })),
          payments: [{ id: 1, method: payMethod, amount_dzd: total, change_dzd: change }],
          customer: customer ? { full_name: customer.full_name, phone: customer.phone } : null,
          boutique_info: {},
        });
        clearCart();
        setShowPay(false);
        setOnline(false);
        flashSuccess("Hors ligne : vente enregistrée localement, elle sera synchronisée au retour du réseau.");
      } else {
        flashError(e?.userMessage || "Vente refusée");
      }
    } finally {
      setBusy(false);
      scanRef.current?.focus();
    }
  };

  const handleFullRefund = async (sale: any) => {
    setBusy(true);
    try {
      const refund = await DesktopCmsApi.posRefundSale(sale.id, { refund_method: "cash" });
      setReceipt(refund);
      setRefundTarget(null);
      flashSuccess(`Remboursement ${refund.sale_reference} — ${fmt(refund.total_dzd)}`);
      loadRegister();
      loadRecentSales();
      onInventoryUpdated?.();
    } catch (e: any) {
      flashError(e?.userMessage || "Remboursement refusé");
    } finally {
      setBusy(false);
    }
  };

  const openSessionsHistory = async () => {
    setSessionsHistory([]);
    try {
      const d = await DesktopCmsApi.posListSessions(30);
      // Closed while loading: stay closed (don't pop the sheet back up).
      setSessionsHistory((prev) => (prev === null ? null : d.items || []));
    } catch (e: any) {
      flashError(e?.userMessage || "Historique indisponible");
      setSessionsHistory(null);
    }
  };

  // Native ESC/POS print when a thermal printer is configured (settings
  // modal); otherwise fall back to the browser's print dialog so the
  // existing on-screen receipt still works in the web preview.
  const printReceipt = async () => {
    if (receipt && isHardwareConfigured()) {
      const r = await printSaleReceipt(receipt as any);
      if (r.ok) {
        flashSuccess("Reçu envoyé à l'imprimante");
      } else {
        flashError(r.error);
        window.print();
      }
    } else {
      // No thermal printer — go straight to the universal system-printer path
      // so the operator gets a proper preview + any Windows printer to pick.
      printReceiptViaSystem();
    }
  };

  // Universal path: render the receipt as a sized HTML page and open the
  // browser/Tauri PDF-preview dialog. The operator can pick ANY installed
  // Windows printer (laser, inkjet, PDF, fax), zoom, change paper size, or
  // Save as PDF. Always available — not just a fallback.
  const printReceiptViaSystem = () => {
    if (!receipt) return;
    const { blocks, paperWidthMm } = buildReceiptBlocks(receipt);

    const r = openSystemPrint({
      title: `Reçu ${receipt.sale_reference || ""}`.trim(),
      paper: { kind: "mm", width: paperWidthMm, height: 297 },  // 58/80mm × receipt-length A4 (printer trims unused area)
      marginMm: 2,
      html: renderReceiptHtml(blocks),
    });
    if (!r.ok) flashError(r.error);
  };

  // Barcode scanner HID hook — scans anywhere on the POS screen route to the
  // same lookup flow as manually typing into the scan box. Disabled while a
  // blocking modal is open so an accidental scan can't insert into a text
  // field inside the modal.
  const scannerEnabled = !showPay && !variantPicker && !showClose && !showPrinterSettings && !refundTarget && !showConflicts && !sessionsHistory && !invoiceSaleId;
  useBarcodeScanner(async (code) => {
    const trimmed = code.trim();
    if (!trimmed) return;
    setScanCode(trimmed);
    try {
      const res = await resolveLookup(trimmed, { online });
      setLastLookupSource(res.source);
      if (res.match_type === "variant") {
        addVariantToCart(res.variant);
        setScanCode("");
      } else if (res.match_type === "product") {
        setVariantPicker(res.results[0]);
      } else if (res.match_type === "search" && res.results.length) {
        setSearchResults(res.results);
      } else {
        flashError(`Aucun produit pour « ${trimmed} »`);
      }
    } catch (e: any) {
      flashError(e?.userMessage || "Recherche échouée");
    }
  }, { enabled: scannerEnabled && Boolean(session) });

  // Mount: initialise the mirror (idempotent) and kick off an incremental
  // sync if we're online. Also expose a refresher the Matériel modal and a
  // toolbar button can call.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const s = await ensureMirrorReady();
      if (!cancelled) setMirrorStat(s);
      if (online && s) {
        setMirrorSyncing(true);
        try {
          await syncCatalog(false);
          if (!cancelled) setMirrorStat(await mirrorStatus());
        } finally {
          if (!cancelled) setMirrorSyncing(false);
        }
      }
    })();
    return () => { cancelled = true; };
    // Only on mount AND when connectivity flips online — avoids a flood of
    // syncs when the online flag bounces.
  }, [online]);

  const refreshMirror = useCallback(async (force = false) => {
    setMirrorSyncing(true);
    try {
      const r = await syncCatalog(force);
      setMirrorStat(await mirrorStatus());
      if (r.ok) {
        flashSuccess(`Catalogue ${r.mode === "snapshot" ? "chargé" : "mis à jour"} (${r.variants_upserted} variantes).`);
      } else {
        flashError(`Sync catalogue : ${r.error ?? "échec"}`);
      }
    } finally {
      setMirrorSyncing(false);
    }
  }, [flashError, flashSuccess]);

  // ------------------------------------------------------------ render
  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-base text-gray-500">
        <RefreshCw className="w-6 h-6 animate-spin mr-3" /> {t("status.loading")}
      </div>
    );
  }

  return (
    <div className="space-y-4 text-sm">
      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2 text-base">
          <AlertTriangle className="w-5 h-5 shrink-0" /> {error}
        </div>
      )}
      {success && (
        <div className="p-4 rounded-2xl bg-emerald-50 border-2 border-emerald-200 text-emerald-800 font-bold flex items-center gap-2 text-base">
          <CheckCircle2 className="w-5 h-5 shrink-0" /> {success}
        </div>
      )}

      {/* ================= SYNC STATUS BAR ================= */}
      {(!online || queueCounts.pending > 0 || queueCounts.conflict > 0 || queueCounts.failed > 0) && (
        <div
          className={`p-3 rounded-2xl flex flex-wrap items-center justify-between gap-2 border-2 ${
            !online
              ? "bg-amber-50 border-amber-200 text-amber-800"
              : queueCounts.conflict > 0
              ? "bg-red-50 border-red-200 text-red-800"
              : "bg-sky-50 border-sky-200 text-sky-800"
          }`}
        >
          <div className="flex items-center gap-2 font-bold">
            {online ? <Wifi className="w-5 h-5" /> : <WifiOff className="w-5 h-5" />}
            <span>{online ? "En ligne" : "Hors ligne"}</span>
            {(queueCounts.pending > 0 || queueCounts.failed > 0) && (
              <span className="font-mono">· {queueCounts.pending + queueCounts.failed} vente(s) en attente</span>
            )}
            {queueCounts.conflict > 0 && (
              <button type="button" onClick={() => setShowConflicts(true)} className="underline font-mono">
                · {queueCounts.conflict} conflit(s) à traiter
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {queueCounts.conflict > 0 && (
              <button type="button" onClick={() => setShowConflicts(true)} className="h-10 px-3 rounded-xl bg-white/60 font-bold flex items-center gap-1.5 active:scale-95">
                <CloudOff className="w-4 h-4" /> Voir conflits
              </button>
            )}
            <button
              type="button"
              disabled={syncing || !online || queueCounts.pending + queueCounts.failed === 0}
              onClick={() => runSync(false)}
              className="h-10 px-4 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-1.5 disabled:opacity-40 active:scale-95"
            >
              {syncing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CloudUpload className="w-4 h-4" />} Synchroniser
            </button>
          </div>
        </div>
      )}

      {/* ================= REGISTER CLOSED: open screen ================= */}
      {!session ? (
        <div className="max-w-sm mx-auto bg-white p-6 rounded-3xl border border-[#D4AF62]/40 shadow-sm mt-4">
          <div className="flex items-center gap-3 mb-1 text-[#063D2E] font-serif font-bold text-xl">
            <span className="w-11 h-11 rounded-2xl bg-[#063D2E]/5 flex items-center justify-center">
              <Lock className="w-6 h-6" />
            </span>
            Caisse fermée
          </div>
          <p className="text-gray-500 mb-4 pl-1">Saisissez le fond de caisse pour commencer la journée.</p>
          <div className="mb-3 p-4 rounded-2xl bg-[#F5F3EE] text-center">
            <div className="text-xs uppercase tracking-wide text-gray-500 font-bold">Fond de caisse</div>
            <div className="text-3xl font-bold text-[#063D2E] font-mono tabular-nums">{fmt(parseInt(openingFloat || "0", 10) || 0)}</div>
          </div>
          <Keypad value={openingFloat} onChange={setOpeningFloat} quickAdds={[1000, 5000, 10000]} />
          <button
            type="button"
            disabled={busy}
            onClick={handleOpenRegister}
            className="mt-4 w-full h-16 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-lg flex items-center justify-center gap-2 disabled:opacity-50 active:scale-[0.99]"
          >
            <Unlock className="w-6 h-6" /> Ouvrir la caisse
          </button>
          <button
            type="button"
            onClick={openSessionsHistory}
            className="mt-2 w-full h-11 rounded-2xl border-2 border-[#063D2E]/10 text-[#063D2E] font-bold flex items-center justify-center gap-2 active:scale-95"
          >
            <History className="w-5 h-5" /> Historique des caisses
          </button>
        </div>
      ) : (
        <>
          {/* ================= REGISTER BANNER ================= */}
          <div className="bg-gradient-to-r from-[#063D2E] to-[#0a5540] text-[#E8D4A5] p-4 rounded-3xl flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-5">
              <div className="flex items-center gap-2 font-serif font-bold text-lg">
                <span className="w-10 h-10 rounded-2xl bg-white/10 flex items-center justify-center">
                  <Unlock className="w-5 h-5 text-[#D4AF62]" />
                </span>
                {session.register_name}
              </div>
              <div className="flex gap-5 text-sm">
                <Stat label="Fond" value={fmt(session.opening_float_dzd)} />
                <Stat label={`Ventes (${session.sales_count || 0})`} value={fmt(session.sales_total_dzd || 0)} />
                <Stat label="Remb." value={fmt(session.refunds_total_dzd || 0)} />
                <Stat label="Caisse attendue" value={fmt(session.expected_cash_dzd || 0)} gold />
              </div>
            </div>
            <div className="flex items-center gap-2">
              {mirrorStat && mirrorStat.initialized && (
                <button
                  type="button"
                  onClick={() => refreshMirror(false)}
                  disabled={mirrorSyncing}
                  className="h-12 px-3 rounded-2xl bg-white/10 hover:bg-white/20 text-[#E8D4A5] font-bold flex items-center gap-2 active:scale-95 disabled:opacity-60"
                  title={`Catalogue local — ${mirrorStat.variant_count} variantes${mirrorStat.last_synced_at ? ` · dernière sync ${new Date(mirrorStat.last_synced_at).toLocaleTimeString("fr-FR")}` : ""}`}
                >
                  <RefreshCw className={`w-4 h-4 ${mirrorSyncing ? "animate-spin" : ""}`} />
                  <span className="font-mono text-xs">
                    {mirrorStat.variant_count}
                    {lastLookupSource === "mirror" && !online && <span className="ml-1 text-amber-300">· hors ligne</span>}
                  </span>
                </button>
              )}
              <button
                type="button"
                onClick={() => setShowPrinterSettings(true)}
                className="h-12 px-4 rounded-2xl bg-white/10 hover:bg-white/20 text-[#E8D4A5] font-bold flex items-center gap-2 active:scale-95"
                title="Imprimante & tiroir-caisse"
              >
                <SettingsIcon className="w-5 h-5" /> {t("pos.hardware")}
              </button>
              <button
                type="button"
                onClick={openSessionsHistory}
                className="h-12 px-4 rounded-2xl bg-white/10 hover:bg-white/20 text-[#E8D4A5] font-bold flex items-center gap-2 active:scale-95"
              >
                <History className="w-5 h-5" /> {t("pos.history")}
              </button>
              <button
                type="button"
                onClick={() => setShowClose(true)}
                className="h-12 px-5 rounded-2xl bg-[#D4AF62] text-[#02291F] font-bold flex items-center gap-2 active:scale-95"
              >
                <Lock className="w-5 h-5" /> {t("pos.close_session")}
              </button>
            </div>
          </div>

          {/* ================= WORKSPACE ================= */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            {/* LEFT: scan + results + recent */}
            <div className="lg:col-span-3 space-y-4">
              <form onSubmit={handleScan} className="bg-white p-4 rounded-3xl border border-[#D4AF62]/40">
                <label className="flex items-center gap-2 font-bold text-[#063D2E] mb-2 text-base">
                  <ScanLine className="w-5 h-5" /> {t("pos.scan_or_search")}
                </label>
                <div className="flex gap-2">
                  <input
                    ref={scanRef}
                    value={scanCode}
                    onChange={(e) => setScanCode(e.target.value)}
                    placeholder="Code-barres, SKU ou nom…"
                    className="flex-1 h-14 px-4 rounded-2xl border-2 border-gray-200 font-mono text-lg focus:border-[#063D2E] outline-none"
                    autoFocus
                    data-barcode-target="true"
                  />
                  <button type="submit" className="h-14 px-6 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
                    <Search className="w-5 h-5" /> Chercher
                  </button>
                </div>
              </form>

              {searchResults.length > 0 && (
                <div className="bg-white p-4 rounded-3xl border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-bold text-[#063D2E] text-base">Résultats</h4>
                    <button aria-label="Effacer les résultats" type="button" onClick={() => setSearchResults([])} className="text-gray-400 hover:text-gray-700">
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {searchResults.map((p) => (
                      <div key={p.id} className="p-3 rounded-2xl border border-gray-200 bg-[#FCFBF8]">
                        <div className="font-bold text-[#063D2E] mb-2">{p.name_fr}</div>
                        <div className="flex flex-wrap gap-2">
                          {(p.variants || []).map((v: any) => (
                            <div key={v.variant_id} className="flex items-stretch rounded-xl border-2 border-[#063D2E]/15 overflow-hidden hover:border-[#063D2E]">
                              <button
                                type="button"
                                disabled={v.stock_qty < 1}
                                onClick={() => addVariantToCart({ ...v, product_name: p.name_fr })}
                                className="min-h-12 px-3 py-2 font-bold text-left disabled:opacity-40 active:scale-95"
                              >
                                <div>{v.variant_title}</div>
                                <div className="text-[#7a5c16] font-mono">
                                  {fmt(v.unit_price_dzd)} · {v.stock_qty} dispo
                                  {!v.barcode && <span className="ml-1 text-amber-700 text-xs"> · sans code-barres</span>}
                                </div>
                              </button>
                              <button
                                type="button"
                                onClick={() => setLabelVariantId(v.variant_id)}
                                title={v.barcode ? "Imprimer l'étiquette" : "Générer un code-barres et imprimer"}
                                className="px-3 border-l-2 border-[#063D2E]/15 bg-white text-[#063D2E] hover:bg-[#063D2E]/5 active:scale-95 flex items-center"
                              >
                                <TagIcon className="w-4 h-4" />
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="bg-white p-4 rounded-3xl border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-bold text-[#063D2E] text-base">Ventes récentes</h4>
                  <button aria-label="Actualiser" type="button" onClick={loadRecentSales} className="w-10 h-10 rounded-xl flex items-center justify-center text-gray-400 hover:text-[#063D2E] active:scale-95">
                    <RefreshCw className="w-5 h-5" />
                  </button>
                </div>
                <div className="space-y-2 max-h-72 overflow-auto">
                  {recentSales.length === 0 && <div className="text-gray-400 py-6 text-center">Aucune vente pour le moment.</div>}
                  {recentSales.map((s) => (
                    <div key={s.id} className="flex items-center justify-between p-3 rounded-2xl border border-gray-100 bg-[#FCFBF8]">
                      <div className="min-w-0">
                        <span className="font-mono font-bold">{s.sale_reference}</span>
                        <span
                          className={`ml-2 px-2 py-0.5 rounded-lg text-xs font-bold ${
                            s.sale_type === "refund"
                              ? "bg-red-100 text-red-700"
                              : s.status === "refunded"
                              ? "bg-gray-200 text-gray-600"
                              : s.status === "partially_refunded"
                              ? "bg-amber-100 text-amber-700"
                              : "bg-emerald-100 text-emerald-700"
                          }`}
                        >
                          {s.sale_type === "refund"
                            ? "Avoir"
                            : ({ completed: "Payé", refunded: "Remboursé", partially_refunded: "Remb. partiel", voided: "Annulé" } as Record<string, string>)[s.status] || s.status}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-base">{fmt(s.total_dzd)}</span>
                        <button
                          type="button"
                          onClick={() => DesktopCmsApi.posGetSale(s.id).then(setReceipt)}
                          className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-500 hover:text-[#063D2E] hover:bg-gray-100 active:scale-95"
                          title="Voir le reçu"
                        >
                          <Printer className="w-5 h-5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setInvoiceSaleId(s.id)}
                          className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-500 hover:text-[#063D2E] hover:bg-gray-100 active:scale-95"
                          title="Facture A4"
                        >
                          <FileTextIcon className="w-5 h-5" />
                        </button>
                        {s.sale_type === "sale" && s.status !== "refunded" && (
                          <button
                            type="button"
                            onClick={() => setRefundTarget(s)}
                            className="w-11 h-11 rounded-xl flex items-center justify-center text-red-500 hover:text-red-700 hover:bg-red-50 active:scale-95"
                            title="Rembourser"
                          >
                            <RotateCcw className="w-5 h-5" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* RIGHT: ticket */}
            <div className="lg:col-span-2 bg-white rounded-3xl border-2 border-[#D4AF62]/40 flex flex-col overflow-hidden shadow-sm">
              <div className="px-4 py-3 bg-[#063D2E] text-[#E8D4A5] flex items-center justify-between">
                <span className="font-serif font-bold text-base flex items-center gap-2">
                  <ShoppingCart className="w-5 h-5" /> Ticket · {itemCount} article{itemCount > 1 ? "s" : ""}
                </span>
                {cart.length > 0 && (
                  <button type="button" onClick={clearCart} className="h-9 px-3 rounded-xl bg-white/10 hover:bg-white/20 font-bold text-sm active:scale-95">
                    Vider
                  </button>
                )}
              </div>

              {/* Customer attach row */}
              <button
                type="button"
                onClick={() => setShowCustomer(true)}
                className="w-full px-4 py-2.5 flex items-center justify-between border-b border-gray-100 hover:bg-[#FCFBF8] active:scale-[0.99]"
              >
                <span className="flex items-center gap-2 font-bold text-[#063D2E]">
                  {customer ? <UserCheck className="w-4 h-4 text-emerald-600" /> : <User className="w-4 h-4 text-gray-400" />}
                  {customer ? `${customer.full_name}` : "Client de passage"}
                </span>
                <span className="text-[11px] text-gray-400 font-mono">{customer ? customer.phone : "Rattacher un client →"}</span>
              </button>

              <div className="flex-1 overflow-auto p-3 space-y-2 min-h-[220px] max-h-[46vh]">
                {cart.length === 0 && (
                  <div className="flex flex-col items-center justify-center h-full text-gray-400 py-10 gap-2">
                    <ScanLine className="w-10 h-10" />
                    <span>Scannez un produit pour commencer.</span>
                  </div>
                )}
                {cart.map((l) => (
                  <div key={l.variant_id} className="p-3 rounded-2xl border border-gray-100 bg-[#FCFBF8]">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="font-bold text-[#063D2E] truncate text-base">{l.product_name}</div>
                        <div className="text-gray-500 font-mono">{l.variant_title} · {fmt(l.unit_price_dzd)}</div>
                      </div>
                      <button type="button" aria-label={`Retirer ${l.product_name} du ticket`} onClick={() => removeLine(l.variant_id)} className="w-10 h-10 rounded-xl flex items-center justify-center text-gray-300 hover:text-red-600 active:scale-95">
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                    <div className="flex items-center justify-between mt-2">
                      <div className="flex items-center gap-2">
                        <button type="button" aria-label="Un de moins" onClick={() => updateQty(l.variant_id, -1)} className="w-12 h-12 rounded-2xl bg-gray-100 flex items-center justify-center active:scale-95">
                          <Minus className="w-5 h-5" />
                        </button>
                        <span className="w-10 text-center font-bold text-xl tabular-nums">{l.quantity}</span>
                        <button type="button" aria-label="Un de plus" onClick={() => updateQty(l.variant_id, 1)} className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-900 flex items-center justify-center active:scale-95">
                          <Plus className="w-5 h-5" />
                        </button>
                      </div>
                      <span className="font-mono font-bold text-lg text-[#063D2E]">
                        {fmt(l.unit_price_dzd * l.quantity - Math.min(l.line_discount_dzd, l.unit_price_dzd * l.quantity))}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <div className="p-4 border-t-2 border-dashed border-gray-200 space-y-2 bg-white">
                <div className="flex justify-between text-gray-500">
                  <span>Sous-total</span>
                  <span className="font-mono">{fmt(subtotal)}</span>
                </div>
                {(lineDiscounts > 0 || orderDisc > 0) && (
                  <div className="flex justify-between text-amber-700">
                    <span>Remises</span>
                    <span className="font-mono">-{fmt(lineDiscounts + orderDisc)}</span>
                  </div>
                )}
                <div className="flex items-center justify-between pt-1">
                  <span className="text-xl font-bold text-[#063D2E]">TOTAL</span>
                  <span className="text-3xl font-extrabold text-[#063D2E] font-mono tabular-nums">{fmt(total)}</span>
                </div>
                <button
                  type="button"
                  disabled={busy || cart.length === 0}
                  onClick={() => {
                    setTendered("");
                    setShowPay(true);
                  }}
                  className="w-full h-16 rounded-2xl bg-gradient-to-r from-[#D4AF62] to-[#E8D4A5] text-[#02291F] font-extrabold text-xl flex items-center justify-center gap-3 disabled:opacity-40 active:scale-[0.99] shadow-sm"
                >
                  <CheckCircle2 className="w-6 h-6" /> {t("pos.checkout")} {fmt(total)}
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ================= PAYMENT SHEET ================= */}
      {showPay && (
        <PaymentSheet
          total={total}
          payMethod={payMethod}
          setPayMethod={setPayMethod}
          orderDiscount={orderDiscount}
          setOrderDiscount={setOrderDiscount}
          tendered={tendered}
          setTendered={setTendered}
          tenderedNum={tenderedNum}
          receivedShown={receivedShown}
          change={change}
          busy={busy}
          handleConfirmSale={handleConfirmSale}
          setShowPay={setShowPay}
        />
      )}

      {/* ================= VARIANT PICKER ================= */}
      {variantPicker && (
        <VariantPickerSheet
          variantPicker={variantPicker}
          setVariantPicker={setVariantPicker}
          addVariantToCart={addVariantToCart}
        />
      )}

      {/* ================= CLOSE REGISTER ================= */}
      {showClose && session && (
        <CloseRegisterSheet
          session={session}
          countedCash={countedCash}
          setCountedCash={setCountedCash}
          busy={busy}
          handleCloseRegister={handleCloseRegister}
          setShowClose={setShowClose}
        />
      )}

      {/* ================= REFUND ================= */}
      {refundTarget && (
        <RefundSheet
          refundTarget={refundTarget}
          busy={busy}
          handleFullRefund={handleFullRefund}
          setRefundTarget={setRefundTarget}
        />
      )}

      {/* ================= SESSIONS HISTORY ================= */}
      {sessionsHistory !== null && (
        <SessionsHistorySheet
          sessionsHistory={sessionsHistory}
          setSessionsHistory={setSessionsHistory}
        />
      )}

      {/* ================= CUSTOMER ATTACH ================= */}
      {showCustomer && (
        <CustomerSheet
          customer={customer}
          setCustomer={setCustomer}
          custQuery={custQuery}
          setCustQuery={setCustQuery}
          searchCustomer={searchCustomer}
          custResults={custResults}
          pickCustomer={pickCustomer}
          custNewName={custNewName}
          setCustNewName={setCustNewName}
          custNewPhone={custNewPhone}
          setCustNewPhone={setCustNewPhone}
          createCustomer={createCustomer}
          setShowCustomer={setShowCustomer}
        />
      )}

      {/* ================= OFFLINE CONFLICTS ================= */}
      {showConflicts && (
        <ConflictsSheet
          queue={queue}
          setShowConflicts={setShowConflicts}
        />
      )}

      {/* ================= RECEIPT ================= */}
      {receipt && <ReceiptModal sale={receipt} onClose={() => setReceipt(null)} onPrint={printReceipt} onSystemPrint={printReceiptViaSystem} />}

      {/* ================= INVOICE A4 ================= */}
      {invoiceSaleId !== null && <InvoiceModal saleId={invoiceSaleId} onClose={() => setInvoiceSaleId(null)} />}

      {/* ================= PRINTER SETTINGS ================= */}
      <PrinterSettingsModal
        open={showPrinterSettings}
        onClose={() => setShowPrinterSettings(false)}
        onFlash={(kind, msg) => (kind === "ok" ? flashSuccess(msg) : flashError(msg))}
      />

      {/* ================= BARCODE / LABEL (inline from search results) ======= */}
      {labelVariantId !== null && (
        <BarcodeLabelModal
          variantId={labelVariantId}
          onClose={() => setLabelVariantId(null)}
          onChanged={() => onInventoryUpdated?.()}
        />
      )}
    </div>
  );
};
