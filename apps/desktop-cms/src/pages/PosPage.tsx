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
  Banknote,
  CreditCard,
  Wallet,
  Delete,
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
import { Wifi, WifiOff, CloudUpload, CloudOff, User, UserPlus, UserCheck } from "lucide-react";
import {
  isHardwareConfigured,
  printSaleReceipt,
  loadHardwareSettings,
  openCashDrawer as kickDrawer,
} from "../utils/posHardware";
import { useBarcodeScanner } from "../utils/useBarcodeScanner";
import { openSystemPrint, renderReceiptHtml, type ReceiptBlock } from "../utils/systemPrint";
import { resolveLookup } from "../utils/posLookupResolver";
import { syncCatalog, ensureMirrorReady } from "../utils/posMirrorSync";
import { mirrorStatus, type MirrorStatus as MirrorStatusType } from "../utils/posMirror";
import { useEscapeToClose } from "../utils/useEscapeToClose";
import { serverDate } from "../utils/serverDate";

// ---------------------------------------------------------------------------
// POS — Touch-first cashier workspace.
// Design tuned for a digital (touchscreen) register per Apple HIG:
//   · Targets >= 48px  (accessibility.md > Interactions: iOS/iPadOS 44x44pt)
//   · Base type 14-16px, totals 24-30px (accessibility.md > Legibility: 17pt default)
//   · Emerald/gold brand kept as the signature; gold reserved for the one
//     primary action (Encaisser). (branding.md: brand color for primary actions)
//   · On-screen numeric keypad for cash entry (no physical keyboard on a till).
// ---------------------------------------------------------------------------

interface RegisterSession {
  id: number;
  register_name: string;
  opening_float_dzd: number;
  expected_cash_dzd?: number;
  sales_total_dzd?: number;
  refunds_total_dzd?: number;
  sales_count?: number;
  opened_at: string;
  status: string;
}

interface LookupVariant {
  variant_id: number;
  product_id: number;
  product_name: string;
  variant_title: string;
  sku: string;
  barcode?: string | null;
  unit_price_dzd: number;
  stock_qty: number;
  main_image_url?: string | null;
}

interface CartLine {
  variant_id: number;
  product_id: number;
  product_name: string;
  variant_title: string;
  sku: string;
  unit_price_dzd: number;
  quantity: number;
  line_discount_dzd: number;
  stock_qty: number;
}

type PaymentMethod = "cash" | "card" | "transfer";

function fmt(dzd: number): string {
  return `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;
}

// ---------------------------------------------------------------------------
// On-screen numeric keypad (touch). 64px keys, brand-consistent.
// ---------------------------------------------------------------------------
const Keypad: React.FC<{
  value: string;
  onChange: (v: string) => void;
  quickAdds?: number[];
  onExact?: () => void;
}> = ({ value, onChange, quickAdds = [1000, 2000, 5000], onExact }) => {
  const press = (d: string) => {
    if (d === "del") {
      onChange(value.slice(0, -1));
    } else {
      const next = (value === "0" ? "" : value) + d;
      onChange(next.replace(/^0+(?=\d)/, "").slice(0, 9));
    }
  };
  const add = (n: number) => onChange(String((parseInt(value || "0", 10) || 0) + n));
  const keyCls =
    "h-16 rounded-2xl bg-white border-2 border-[#063D2E]/10 text-2xl font-bold text-[#063D2E] active:scale-95 active:bg-[#F5F3EE] transition-transform flex items-center justify-center select-none";
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        {quickAdds.map((n) => (
          <button key={n} type="button" onClick={() => add(n)} className="flex-1 h-12 rounded-xl bg-[#063D2E]/5 text-[#063D2E] font-bold text-sm active:scale-95">
            +{n.toLocaleString("fr-DZ")}
          </button>
        ))}
        {onExact && (
          <button type="button" onClick={onExact} className="flex-1 h-12 rounded-xl bg-[#D4AF62]/20 text-[#7a5c16] font-bold text-sm active:scale-95">
            Exact
          </button>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
          <button key={d} type="button" onClick={() => press(d)} className={keyCls}>
            {d}
          </button>
        ))}
        <button type="button" onClick={() => press("00")} className={keyCls}>
          00
        </button>
        <button type="button" onClick={() => press("0")} className={keyCls}>
          0
        </button>
        <button aria-label="Effacer le dernier chiffre" type="button" onClick={() => press("del")} className={`${keyCls} text-[#B91C1C]`}>
          <Delete className="w-7 h-7" />
        </button>
      </div>
    </div>
  );
};

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

  const setLineDiscount = (variantId: number, value: string) => {
    const d = Math.max(0, parseInt(value || "0", 10) || 0);
    setCart((prev) => prev.map((l) => (l.variant_id === variantId ? { ...l, line_discount_dzd: d } : l)));
  };

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
      setSessionsHistory(d.items || []);
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
    const b = receipt.boutique_info || {};
    const width = loadHardwareSettings().line_width ?? 32;
    const paperWidthMm = width >= 42 ? 80 : 58;
    const blocks: ReceiptBlock[] = [];
    blocks.push({ text: (b.name || "Mus Luxury"), align: "center", bold: true, size: "lg" });
    if (b.legal_name && b.legal_name !== b.name) blocks.push({ text: b.legal_name, align: "center", size: "sm" });
    if (b.address) blocks.push({ text: b.address, align: "center", size: "sm" });
    if (b.phone)   blocks.push({ text: `Tél: ${b.phone}`, align: "center", size: "sm" });
    for (const [label, v] of [["NIF", b.nif], ["NIS", b.nis], ["RC", b.rc], ["Art.", b.article]] as const) {
      if (v) blocks.push({ text: `${label}: ${v}`, align: "center", size: "sm" });
    }
    blocks.push({ rule: true });
    blocks.push({ left: "Ticket", right: receipt.sale_reference || "—", bold: true });
    blocks.push({ left: "Date", right: receipt.created_at ? serverDate(receipt.created_at).toLocaleString("fr-FR") : "—" });
    if (receipt.customer?.full_name) blocks.push({ left: "Client", right: receipt.customer.full_name });
    if (receipt.offline) blocks.push({ text: "** HORS LIGNE — à synchroniser **", align: "center", bold: true });
    if (receipt.sale_type === "refund") blocks.push({ text: "** REMBOURSEMENT **", align: "center", bold: true });
    blocks.push({ rule: true });
    for (const it of receipt.items ?? []) {
      const name = `${it.product_name ?? ""}${it.variant_title ? " · " + it.variant_title : ""}`.trim();
      const qty = Number(it.quantity ?? 0);
      const lineTotal = Number(it.line_total_dzd ?? (Number(it.unit_price_dzd ?? 0) * qty));
      blocks.push({ left: name, right: fmt(lineTotal) });
      if (qty > 1 || it.unit_price_dzd) blocks.push({ left: `  ${qty} × ${fmt(it.unit_price_dzd)}`, size: "sm" });
    }
    blocks.push({ rule: true });
    if (receipt.subtotal_dzd != null) blocks.push({ left: "Sous-total", right: fmt(receipt.subtotal_dzd) });
    if ((receipt.discount_dzd ?? 0) > 0) blocks.push({ left: "Remise", right: `- ${fmt(receipt.discount_dzd)}` });
    if ((receipt.tax_dzd ?? 0) > 0) blocks.push({ left: "TVA", right: fmt(receipt.tax_dzd) });
    blocks.push({ left: "TOTAL", right: fmt(receipt.total_dzd), bold: true, size: "xl" });
    if ((receipt.payments ?? []).length) {
      blocks.push({ rule: true });
      for (const p of receipt.payments) {
        const label = p.method === "cash" ? "Espèces" : p.method === "card" ? "Carte" : p.method === "transfer" ? "Virement" : (p.method ?? "");
        blocks.push({ left: label, right: fmt(p.amount_dzd) });
        if ((p.change_dzd ?? 0) > 0) blocks.push({ left: "Monnaie", right: fmt(p.change_dzd) });
      }
    }
    blocks.push({ rule: true });
    blocks.push({ text: b.footer_line || `Merci de votre visite — ${b.name || "Mus Luxury"}`, align: "center", size: "sm" });

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
        <Sheet onClose={() => setShowPay(false)} title={`Encaisser ${fmt(total)}`}>
          <div className="grid grid-cols-3 gap-2 mb-4">
            {([
              ["cash", "Espèces", Banknote],
              ["card", "Carte", CreditCard],
              ["transfer", "Virement", Wallet],
            ] as [PaymentMethod, string, any][]).map(([m, label, Icon]) => (
              <button
                key={m}
                type="button"
                onClick={() => setPayMethod(m)}
                className={`h-20 rounded-2xl border-2 font-bold flex flex-col items-center justify-center gap-1 active:scale-95 ${
                  payMethod === m ? "bg-[#063D2E] text-[#D4AF62] border-[#063D2E]" : "border-gray-200 text-gray-600"
                }`}
              >
                <Icon className="w-6 h-6" /> {label}
              </button>
            ))}
          </div>

          <div className="flex items-center justify-between mb-3">
            <span className="text-gray-500 font-bold">Remise globale</span>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={0}
                value={orderDiscount}
                onChange={(e) => setOrderDiscount(e.target.value)}
                placeholder="0"
                className="w-28 h-11 px-3 rounded-xl border-2 border-gray-200 font-mono text-right text-base"
              />
              <span className="text-gray-400">DA</span>
            </div>
          </div>

          {payMethod === "cash" ? (
            <>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div className="p-3 rounded-2xl bg-[#F5F3EE] text-center">
                  <div className="text-xs uppercase tracking-wide text-gray-500 font-bold">Reçu</div>
                  <div className="text-2xl font-bold text-[#063D2E] font-mono tabular-nums">{fmt(receivedShown)}</div>
                  {tenderedNum === 0 && <div className="text-[11px] text-gray-500">montant exact</div>}
                </div>
                <div className={`p-3 rounded-2xl text-center ${receivedShown >= total ? "bg-emerald-50" : "bg-red-50"}`}>
                  <div className="text-xs uppercase tracking-wide text-gray-500 font-bold">Monnaie</div>
                  <div className={`text-2xl font-bold font-mono tabular-nums ${receivedShown >= total ? "text-emerald-700" : "text-red-600"}`}>
                    {receivedShown >= total ? fmt(change) : `-${fmt(total - receivedShown)}`}
                  </div>
                </div>
              </div>
              <Keypad value={tendered} onChange={setTendered} quickAdds={[1000, 2000, 5000]} onExact={() => setTendered(String(total))} />
            </>
          ) : (
            <div className="p-4 rounded-2xl bg-[#F5F3EE] text-center mb-2">
              <div className="text-gray-500">Montant à encaisser</div>
              <div className="text-3xl font-extrabold text-[#063D2E] font-mono tabular-nums">{fmt(total)}</div>
            </div>
          )}

          <button
            type="button"
            disabled={busy || (payMethod === "cash" && tenderedNum > 0 && tenderedNum < total)}
            onClick={handleConfirmSale}
            className="mt-4 w-full h-16 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-xl flex items-center justify-center gap-3 disabled:opacity-40 active:scale-[0.99]"
          >
            <CheckCircle2 className="w-6 h-6" /> Valider la vente
          </button>
        </Sheet>
      )}

      {/* ================= VARIANT PICKER ================= */}
      {variantPicker && (
        <Sheet onClose={() => setVariantPicker(null)} title={variantPicker.name_fr}>
          <div className="grid grid-cols-2 gap-3">
            {(variantPicker.variants || []).map((v: any) => (
              <button
                key={v.variant_id}
                type="button"
                disabled={v.stock_qty < 1}
                onClick={() => addVariantToCart({ ...v, product_name: variantPicker.name_fr })}
                className="min-h-16 p-3 rounded-2xl border-2 border-[#063D2E]/15 font-bold text-left disabled:opacity-40 active:scale-95 hover:border-[#063D2E]"
              >
                <div className="text-base">{v.variant_title}</div>
                <div className="text-[#7a5c16] font-mono">{fmt(v.unit_price_dzd)} · {v.stock_qty} dispo</div>
              </button>
            ))}
          </div>
        </Sheet>
      )}

      {/* ================= CLOSE REGISTER ================= */}
      {showClose && session && (
        <Sheet onClose={() => setShowClose(false)} title="Clôturer la caisse">
          <div className="p-3 rounded-2xl bg-[#F5F3EE] mb-3 text-center">
            <div className="text-xs uppercase tracking-wide text-gray-500 font-bold">Caisse attendue</div>
            <div className="text-2xl font-bold text-[#063D2E] font-mono">{fmt(session.expected_cash_dzd || 0)}</div>
            <div className="text-xs text-gray-400 mt-1">Fond {fmt(session.opening_float_dzd)} + ventes espèces</div>
          </div>
          <div className="p-3 rounded-2xl bg-white border-2 border-gray-100 mb-3 text-center">
            <div className="text-xs uppercase tracking-wide text-gray-500 font-bold">Espèces comptées</div>
            <div className="text-2xl font-bold text-[#063D2E] font-mono tabular-nums">{fmt(parseInt(countedCash || "0", 10) || 0)}</div>
          </div>
          <Keypad value={countedCash} onChange={setCountedCash} quickAdds={[1000, 5000, 10000]} onExact={() => setCountedCash(String(session.expected_cash_dzd || 0))} />
          <button
            type="button"
            disabled={busy}
            onClick={handleCloseRegister}
            className="mt-4 w-full h-16 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-lg disabled:opacity-50 active:scale-[0.99]"
          >
            Confirmer la clôture
          </button>
        </Sheet>
      )}

      {/* ================= REFUND ================= */}
      {refundTarget && (
        <Sheet onClose={() => setRefundTarget(null)} title={`Rembourser ${refundTarget.sale_reference}`}>
          <p className="text-gray-600 mb-4 text-base">
            Rembourse l'intégralité des articles encore remboursables ({fmt(refundTarget.total_dzd)}). Le stock est réintégré automatiquement.
          </p>
          <button
            type="button"
            disabled={busy}
            onClick={() => handleFullRefund(refundTarget)}
            className="w-full h-16 rounded-2xl bg-red-600 text-white font-extrabold text-lg disabled:opacity-50 flex items-center justify-center gap-2 active:scale-[0.99]"
          >
            <RotateCcw className="w-6 h-6" /> Confirmer le remboursement
          </button>
        </Sheet>
      )}

      {/* ================= SESSIONS HISTORY ================= */}
      {sessionsHistory !== null && (
        <Sheet onClose={() => setSessionsHistory(null)} title="Historique des caisses">
          <div className="space-y-2 max-h-[60vh] overflow-auto">
            {sessionsHistory.length === 0 && <div className="text-gray-400 py-6 text-center">Aucune session.</div>}
            {sessionsHistory.map((s) => (
              <div key={s.id} className="p-3 rounded-2xl border border-gray-100 bg-[#FCFBF8]">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[#063D2E]">#{s.id} · {s.register_name}</span>
                  <span className={`px-2 py-0.5 rounded-lg text-xs font-bold ${s.status === "open" ? "bg-emerald-100 text-emerald-700" : "bg-gray-200 text-gray-600"}`}>
                    {s.status === "open" ? "Ouverte" : "Clôturée"}
                  </span>
                </div>
                <div className="text-gray-500 mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-[11px]">
                  <span>Fond: {fmt(s.opening_float_dzd)}</span>
                  <span>Ventes: {fmt(s.total_sales_dzd || 0)}</span>
                  {(s.total_refunds_dzd || 0) > 0 && <span>Remb.: {fmt(s.total_refunds_dzd)}</span>}
                  {s.status === "open" && <span>Caisse attendue: {fmt(s.expected_cash_dzd || 0)}</span>}
                  {s.status === "closed" && <span>Attendu: {fmt(s.expected_cash_dzd || 0)}</span>}
                  {s.status === "closed" && <span>Compté: {fmt(s.counted_cash_dzd || 0)}</span>}
                  {s.status === "closed" && (
                    <span className={`col-span-2 font-bold ${(s.variance_dzd || 0) === 0 ? "text-emerald-600" : "text-amber-700"}`}>
                      Écart: {(s.variance_dzd || 0) >= 0 ? "+" : ""}{fmt(s.variance_dzd || 0)}
                    </span>
                  )}
                </div>
                {s.opened_by_name && <div className="text-gray-400 text-[11px] mt-1">Ouverte par {s.opened_by_name}{s.closed_by_name ? ` · clôturée par ${s.closed_by_name}` : ""}</div>}
              </div>
            ))}
          </div>
        </Sheet>
      )}

      {/* ================= CUSTOMER ATTACH ================= */}
      {showCustomer && (
        <Sheet onClose={() => setShowCustomer(false)} title="Rattacher un client">
          {customer && (
            <div className="mb-3 p-3 rounded-2xl bg-emerald-50 border-2 border-emerald-200 flex items-center justify-between">
              <span className="font-bold text-emerald-800 flex items-center gap-2"><UserCheck className="w-4 h-4" /> {customer.full_name} · {customer.phone}</span>
              <button type="button" onClick={() => setCustomer(null)} className="text-emerald-700 font-bold text-sm underline">Retirer</button>
            </div>
          )}
          <form onSubmit={(e) => { e.preventDefault(); searchCustomer(); }} className="flex gap-2 mb-2">
            <input
              value={custQuery}
              onChange={(e) => setCustQuery(e.target.value)}
              placeholder="Nom ou téléphone…"
              className="flex-1 h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none"
              autoFocus
            />
            <button type="submit" className="h-12 px-4 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold active:scale-95">Chercher</button>
          </form>
          <div className="space-y-1 max-h-48 overflow-auto mb-3">
            {custResults.map((c) => (
              <button key={c.id} type="button" onClick={() => pickCustomer(c)} className="w-full text-left p-2.5 rounded-xl border border-gray-100 hover:bg-[#FCFBF8] flex items-center justify-between active:scale-[0.99]">
                <span className="font-bold text-[#063D2E]">{c.full_name}</span>
                <span className="font-mono text-gray-500 text-[11px]">{c.phone}</span>
              </button>
            ))}
          </div>
          <div className="border-t pt-3">
            <div className="font-bold text-[#063D2E] mb-2 flex items-center gap-2"><UserPlus className="w-4 h-4" /> Nouveau client</div>
            <div className="grid grid-cols-2 gap-2">
              <input value={custNewName} onChange={(e) => setCustNewName(e.target.value)} placeholder="Nom complet" className="h-12 px-3 rounded-2xl border-2 border-gray-200" />
              <input value={custNewPhone} onChange={(e) => setCustNewPhone(e.target.value)} placeholder="Téléphone" className="h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" />
            </div>
            <button type="button" onClick={createCustomer} className="mt-2 w-full h-12 rounded-2xl bg-[#D4AF62] text-[#02291F] font-bold active:scale-95">
              Créer et rattacher
            </button>
          </div>
        </Sheet>
      )}

      {/* ================= OFFLINE CONFLICTS ================= */}
      {showConflicts && (
        <Sheet onClose={() => setShowConflicts(false)} title="Ventes en conflit">
          <p className="text-gray-600 mb-3">
            Ces ventes hors-ligne ont été refusées par le serveur (souvent un stock déjà vendu en ligne). Elles ne sont pas perdues — traitez-les manuellement.
          </p>
          <div className="space-y-2 max-h-[55vh] overflow-auto">
            {queue.filter((i) => i.status === "conflict").length === 0 && (
              <div className="text-gray-400 py-6 text-center">Aucun conflit.</div>
            )}
            {queue
              .filter((i) => i.status === "conflict")
              .map((i) => (
                <div key={i.client_txn_id} className="p-3 rounded-2xl border-2 border-red-100 bg-red-50/40">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-[#063D2E]">{fmt(i.total_dzd)}</span>
                    <span className="text-xs text-gray-400">{serverDate(i.created_at).toLocaleString("fr-FR")}</span>
                  </div>
                  <div className="text-red-600 text-[13px] mt-1">{i.error}</div>
                  <div className="text-gray-500 text-[11px] mt-1">
                    {i.payload.items.map((it) => `${it.quantity}× #${it.variant_id}`).join(", ")}
                  </div>
                </div>
              ))}
          </div>
        </Sheet>
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

// ---------------------------------------------------------------------------
const Stat: React.FC<{ label: string; value: string; gold?: boolean }> = ({ label, value, gold }) => (
  <div>
    <div className="text-[11px] uppercase tracking-wide opacity-70">{label}</div>
    <div className={`font-bold font-mono tabular-nums ${gold ? "text-[#D4AF62]" : ""}`}>{value}</div>
  </div>
);

// Bottom sheet — large, touch-dismissable (modality.md: one task, obvious way out)
const Sheet: React.FC<{ title: string; onClose: () => void; children: React.ReactNode }> = ({ title, onClose, children }) => {
  useEscapeToClose(onClose);
  return (
  <div className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center z-50 p-0 sm:p-4" onClick={onClose}>
    <div
      className="bg-white rounded-t-3xl sm:rounded-3xl p-5 w-full sm:max-w-md max-h-[92vh] overflow-auto"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-serif font-bold text-[#063D2E] text-lg">{title}</h3>
        <button aria-label="Fermer" type="button" onClick={onClose} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-100 active:scale-95">
          <X className="w-6 h-6" />
        </button>
      </div>
      {children}
    </div>
  </div>
);
};

const ReceiptModal: React.FC<{ sale: any; onClose: () => void; onPrint: () => void; onSystemPrint?: () => void }> = ({ sale, onClose, onPrint, onSystemPrint }) => {
  useEscapeToClose(onClose);
  const b = sale.boutique_info || {};
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-3xl w-full max-w-sm max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div id="pos-receipt" className="p-6 font-mono text-sm text-gray-800">
          <div className="text-center mb-2">
            <div className="font-bold text-base">{b.name || "Mus Luxury"}</div>
            {b.legal_name && b.legal_name !== b.name && <div className="text-xs">{b.legal_name}</div>}
            {b.address && <div className="text-xs">{b.address}</div>}
            {b.phone && <div className="text-xs">Tél: {b.phone}</div>}
            {(b.nif || b.nis || b.rc || b.article) && (
              <div className="text-xs mt-1">
                {b.nif && <div>NIF: {b.nif}</div>}
                {b.nis && <div>NIS: {b.nis}</div>}
                {b.rc && <div>RC: {b.rc}</div>}
                {b.article && <div>Art.: {b.article}</div>}
              </div>
            )}
          </div>
          <div className="border-t border-dashed my-2" />
          <div>Reçu: {sale.sale_reference}</div>
          <div>{serverDate(sale.created_at).toLocaleString("fr-FR")}</div>
          {sale.cashier_name && <div>Caissier: {sale.cashier_name}</div>}
          {sale.customer && <div>Client: {sale.customer.full_name}</div>}
          {sale.offline && <div className="font-bold text-amber-700">** HORS LIGNE — à synchroniser **</div>}
          {sale.sale_type === "refund" && <div className="font-bold text-red-700">** REMBOURSEMENT **</div>}
          <div className="border-t border-dashed my-2" />
          {(sale.items || []).map((it: any) => (
            <div key={it.id} className="flex justify-between">
              <span className="truncate pr-2">
                {it.quantity}× {it.product_name} ({it.variant_title})
              </span>
              <span>{fmt(it.line_total_dzd)}</span>
            </div>
          ))}
          <div className="border-t border-dashed my-2" />
          <div className="flex justify-between">
            <span>Sous-total</span>
            <span>{fmt(sale.subtotal_dzd)}</span>
          </div>
          {sale.discount_dzd > 0 && (
            <div className="flex justify-between">
              <span>Remise</span>
              <span>-{fmt(sale.discount_dzd)}</span>
            </div>
          )}
          {sale.tax_dzd > 0 && (
            <div className="flex justify-between">
              <span>Taxe</span>
              <span>{fmt(sale.tax_dzd)}</span>
            </div>
          )}
          <div className="flex justify-between font-bold text-base">
            <span>TOTAL</span>
            <span>{fmt(sale.total_dzd)}</span>
          </div>
          <div className="border-t border-dashed my-2" />
          {(sale.payments || []).map((p: any) => (
            <div key={p.id} className="flex justify-between">
              <span>{p.method === "cash" ? "Espèces" : p.method === "card" ? "Carte" : p.method === "transfer" ? "Virement" : p.method}</span>
              <span>{fmt(p.amount_dzd)}</span>
            </div>
          ))}
          {(sale.payments || []).some((p: any) => p.change_dzd > 0) && (
            <div className="flex justify-between">
              <span>Monnaie</span>
              <span>{fmt((sale.payments || []).reduce((s: number, p: any) => s + (p.change_dzd || 0), 0))}</span>
            </div>
          )}
          <div className="text-center mt-4 text-xs">{b.footer_line || `Merci de votre visite — ${b.name || "Mus Luxury"}`}</div>
        </div>
        <div className="p-4 border-t space-y-2 print:hidden">
          <div className="flex gap-2">
            <button type="button" onClick={onPrint} className="flex-1 h-14 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center justify-center gap-2 active:scale-95">
              <Printer className="w-5 h-5" /> Imprimer
            </button>
            <button type="button" onClick={onClose} className="flex-1 h-14 rounded-2xl bg-gray-100 font-bold active:scale-95">
              Fermer
            </button>
          </div>
          {onSystemPrint && (
            <button
              type="button"
              onClick={onSystemPrint}
              className="w-full h-11 rounded-2xl border-2 border-gray-200 text-gray-700 font-bold text-sm flex items-center justify-center gap-2 active:scale-95"
              title="Ouvrir l'aperçu système (toute imprimante Windows, ajuster la taille)"
            >
              <Printer className="w-4 h-4" /> Aperçu système (toute imprimante)
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
