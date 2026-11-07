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
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";

// ---------------------------------------------------------------------------
// Types
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

const GOLD = "#D4AF62";
const GREEN = "#063D2E";

function fmt(dzd: number): string {
  return `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;
}

export const PosPage: React.FC<{ onInventoryUpdated?: () => void }> = ({ onInventoryUpdated }) => {
  const [session, setSession] = useState<RegisterSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Register open/close
  const [openingFloat, setOpeningFloat] = useState("");
  const [countedCash, setCountedCash] = useState("");
  const [showClose, setShowClose] = useState(false);
  const [busy, setBusy] = useState(false);

  // Scan / search
  const [scanCode, setScanCode] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [variantPicker, setVariantPicker] = useState<any | null>(null);
  const scanRef = useRef<HTMLInputElement>(null);

  // Cart
  const [cart, setCart] = useState<CartLine[]>([]);
  const [orderDiscount, setOrderDiscount] = useState("");
  const [payMethod, setPayMethod] = useState<PaymentMethod>("cash");
  const [tendered, setTendered] = useState("");

  // Receipt + recent sales
  const [receipt, setReceipt] = useState<any | null>(null);
  const [recentSales, setRecentSales] = useState<any[]>([]);
  const [refundTarget, setRefundTarget] = useState<any | null>(null);

  // ---------------------------------------------------------------- data load
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

  // ---------------------------------------------------------------- register
  const handleOpenRegister = async () => {
    const amount = parseInt(openingFloat || "0", 10);
    if (isNaN(amount) || amount < 0) return flashError("Fond de caisse invalide");
    setBusy(true);
    try {
      const s = await DesktopCmsApi.posRegisterOpen(amount, "Caisse principale");
      setSession(s);
      setOpeningFloat("");
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
      setCountedCash("");
      flashSuccess(
        `Caisse clôturée. Attendu ${fmt(closed.expected_cash_dzd)}, compté ${fmt(closed.counted_cash_dzd)}, écart ${variance >= 0 ? "+" : ""}${fmt(variance)}`
      );
    } catch (e: any) {
      flashError(e?.userMessage || "Clôture refusée");
    } finally {
      setBusy(false);
    }
  };

  // ---------------------------------------------------------------- scanning
  const addVariantToCart = (v: LookupVariant) => {
    setCart((prev) => {
      const existing = prev.find((l) => l.variant_id === v.variant_id);
      if (existing) {
        if (existing.quantity + 1 > v.stock_qty) {
          flashError(`Stock insuffisant pour ${v.product_name} (${v.variant_title}): ${v.stock_qty} dispo`);
          return prev;
        }
        return prev.map((l) =>
          l.variant_id === v.variant_id ? { ...l, quantity: l.quantity + 1 } : l
        );
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

  const handleScan = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const code = scanCode.trim();
    if (!code) return;
    try {
      const res = await DesktopCmsApi.posLookup(code);
      if (res.match_type === "variant") {
        addVariantToCart(res.variant);
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

  // ---------------------------------------------------------------- cart math
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

  const removeLine = (variantId: number) =>
    setCart((prev) => prev.filter((l) => l.variant_id !== variantId));

  const setLineDiscount = (variantId: number, value: string) => {
    const d = Math.max(0, parseInt(value || "0", 10) || 0);
    setCart((prev) => prev.map((l) => (l.variant_id === variantId ? { ...l, line_discount_dzd: d } : l)));
  };

  const subtotal = cart.reduce((s, l) => s + l.unit_price_dzd * l.quantity, 0);
  const lineDiscounts = cart.reduce((s, l) => s + Math.min(l.line_discount_dzd, l.unit_price_dzd * l.quantity), 0);
  const orderDisc = Math.min(parseInt(orderDiscount || "0", 10) || 0, subtotal - lineDiscounts);
  const total = subtotal - lineDiscounts - orderDisc;
  const tenderedNum = parseInt(tendered || "0", 10) || 0;
  const change = payMethod === "cash" ? Math.max(0, tenderedNum - total) : 0;

  const clearCart = () => {
    setCart([]);
    setOrderDiscount("");
    setTendered("");
    setPayMethod("cash");
  };

  // ---------------------------------------------------------------- checkout
  const handleConfirmSale = async () => {
    if (!cart.length) return flashError("Panier vide");
    if (total <= 0) return flashError("Total invalide");
    if (payMethod === "cash" && tenderedNum > 0 && tenderedNum < total) {
      return flashError("Montant reçu inférieur au total");
    }
    setBusy(true);
    const idemKey = `pos-sale-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    try {
      const payload = {
        items: cart.map((l) => ({
          variant_id: l.variant_id,
          quantity: l.quantity,
          line_discount_dzd: l.line_discount_dzd || 0,
        })),
        payments: [
          {
            method: payMethod,
            amount_dzd: total,
            tendered_dzd: payMethod === "cash" && tenderedNum > 0 ? tenderedNum : undefined,
          },
        ],
        order_discount_dzd: orderDisc,
      };
      const sale = await DesktopCmsApi.posCreateSale(payload, idemKey);
      setReceipt(sale);
      clearCart();
      flashSuccess(`Vente ${sale.sale_reference} enregistrée — ${fmt(sale.total_dzd)}`);
      loadRegister();
      loadRecentSales();
      onInventoryUpdated?.();
    } catch (e: any) {
      flashError(e?.userMessage || "Vente refusée");
    } finally {
      setBusy(false);
      scanRef.current?.focus();
    }
  };

  // ---------------------------------------------------------------- refunds
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

  const printReceipt = () => window.print();

  // ---------------------------------------------------------------- render
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-sm text-gray-500">
        <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Chargement de la caisse…
      </div>
    );
  }

  return (
    <div className="space-y-4 text-xs">
      {error && (
        <div className="p-3 rounded-xl bg-red-100 border border-red-300 text-red-900 font-bold flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" /> {error}
        </div>
      )}
      {success && (
        <div className="p-3 rounded-xl bg-emerald-100 border border-emerald-300 text-emerald-900 font-bold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" /> {success}
        </div>
      )}

      {/* REGISTER BANNER */}
      {!session ? (
        <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 max-w-md">
          <div className="flex items-center gap-2 mb-3 text-[#063D2E] font-serif font-bold text-base">
            <Lock className="w-5 h-5" /> Caisse fermée
          </div>
          <p className="text-gray-500 mb-4">Ouvrez la caisse avec le fond de départ pour commencer à vendre.</p>
          <label className="block font-bold mb-1 text-[#063D2E]">Fond de caisse (DA)</label>
          <div className="flex gap-2">
            <input
              type="number"
              min={0}
              value={openingFloat}
              onChange={(e) => setOpeningFloat(e.target.value)}
              placeholder="0"
              className="flex-1 px-3 py-2 rounded-xl border border-gray-300 font-mono"
            />
            <button
              type="button"
              disabled={busy}
              onClick={handleOpenRegister}
              className="px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 disabled:opacity-50"
            >
              <Unlock className="w-4 h-4" /> Ouvrir
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-gradient-to-r from-[#063D2E] to-[#0a5540] text-[#E8D4A5] p-4 rounded-2xl flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 font-serif font-bold text-base">
              <Unlock className="w-5 h-5 text-[#D4AF62]" /> {session.register_name}
            </div>
            <div className="flex gap-4 text-[11px]">
              <span>Fond: <strong>{fmt(session.opening_float_dzd)}</strong></span>
              <span>Ventes: <strong>{fmt(session.sales_total_dzd || 0)}</strong> ({session.sales_count || 0})</span>
              <span>Remb.: <strong>{fmt(session.refunds_total_dzd || 0)}</strong></span>
              <span className="text-[#D4AF62]">Caisse attendue: <strong>{fmt(session.expected_cash_dzd || 0)}</strong></span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowClose(true)}
            className="px-4 py-2 rounded-xl bg-[#D4AF62] text-[#02291F] font-bold flex items-center gap-2"
          >
            <Lock className="w-4 h-4" /> Clôturer la caisse
          </button>
        </div>
      )}

      {/* POS WORKSPACE */}
      {session && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          {/* LEFT: scan + search results */}
          <div className="lg:col-span-3 space-y-3">
            <form onSubmit={handleScan} className="bg-white p-4 rounded-2xl border border-[#D4AF62]/40">
              <label className="flex items-center gap-2 font-bold text-[#063D2E] mb-2">
                <ScanLine className="w-4 h-4" /> Scanner un code-barres ou chercher
              </label>
              <div className="flex gap-2">
                <input
                  ref={scanRef}
                  value={scanCode}
                  onChange={(e) => setScanCode(e.target.value)}
                  placeholder="Code-barres, SKU ou nom du produit…"
                  className="flex-1 px-3 py-2.5 rounded-xl border border-gray-300 font-mono"
                  autoFocus
                />
                <button type="submit" className="px-4 py-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2">
                  <Search className="w-4 h-4" /> Chercher
                </button>
              </div>
            </form>

            {searchResults.length > 0 && (
              <div className="bg-white p-3 rounded-2xl border border-gray-200 grid grid-cols-1 sm:grid-cols-2 gap-2">
                {searchResults.map((p) => (
                  <div key={p.id} className="p-2 rounded-xl border border-gray-200">
                    <div className="font-bold text-[#063D2E] mb-1">{p.name_fr}</div>
                    <div className="flex flex-wrap gap-1">
                      {(p.variants || []).map((v: any) => (
                        <button
                          key={v.variant_id}
                          type="button"
                          disabled={v.stock_qty < 1}
                          onClick={() => addVariantToCart({ ...v, product_name: p.name_fr })}
                          className="px-2 py-1 rounded-lg border text-[11px] font-bold disabled:opacity-40 hover:bg-[#063D2E] hover:text-[#D4AF62]"
                        >
                          {v.variant_title} · {fmt(v.unit_price_dzd)} · {v.stock_qty} dispo
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Recent sales + refund */}
            <div className="bg-white p-4 rounded-2xl border border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-bold text-[#063D2E]">Ventes récentes</h4>
                <button type="button" onClick={loadRecentSales} className="text-gray-400 hover:text-[#063D2E]">
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>
              <div className="space-y-1 max-h-56 overflow-auto">
                {recentSales.length === 0 && <div className="text-gray-400">Aucune vente pour le moment.</div>}
                {recentSales.map((s) => (
                  <div key={s.id} className="flex items-center justify-between p-2 rounded-lg border border-gray-100">
                    <div>
                      <span className="font-mono font-bold">{s.sale_reference}</span>{" "}
                      <span className={`ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${s.sale_type === "refund" ? "bg-red-100 text-red-700" : s.status === "refunded" ? "bg-gray-200 text-gray-600" : s.status === "partially_refunded" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>
                        {s.sale_type === "refund" ? "Remboursement" : s.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold">{fmt(s.total_dzd)}</span>
                      <button
                        type="button"
                        onClick={() => DesktopCmsApi.posGetSale(s.id).then(setReceipt)}
                        className="text-gray-400 hover:text-[#063D2E]"
                        title="Voir le reçu"
                      >
                        <Printer className="w-3.5 h-3.5" />
                      </button>
                      {s.sale_type === "sale" && s.status !== "refunded" && (
                        <button
                          type="button"
                          onClick={() => setRefundTarget(s)}
                          className="text-red-400 hover:text-red-700"
                          title="Rembourser"
                        >
                          <RotateCcw className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* RIGHT: cart + payment */}
          <div className="lg:col-span-2 bg-white rounded-2xl border border-[#D4AF62]/40 flex flex-col">
            <div className="p-3 border-b flex items-center justify-between">
              <span className="font-serif font-bold text-[#063D2E] flex items-center gap-2">
                <ShoppingCart className="w-4 h-4" /> Panier ({cart.length})
              </span>
              {cart.length > 0 && (
                <button type="button" onClick={clearCart} className="text-gray-400 hover:text-red-600 text-[11px] font-bold">
                  Vider
                </button>
              )}
            </div>

            <div className="flex-1 overflow-auto p-3 space-y-2 min-h-[160px] max-h-[340px]">
              {cart.length === 0 && (
                <div className="text-gray-400 text-center py-8">Scannez un produit pour commencer.</div>
              )}
              {cart.map((l) => (
                <div key={l.variant_id} className="p-2 rounded-xl border border-gray-100">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-bold text-[#063D2E] truncate">{l.product_name}</div>
                      <div className="text-gray-500 font-mono text-[11px]">{l.variant_title} · {fmt(l.unit_price_dzd)}</div>
                    </div>
                    <button type="button" onClick={() => removeLine(l.variant_id)} className="text-gray-300 hover:text-red-600">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="flex items-center justify-between mt-1.5">
                    <div className="flex items-center gap-1">
                      <button type="button" onClick={() => updateQty(l.variant_id, -1)} className="w-6 h-6 rounded bg-gray-100 font-bold flex items-center justify-center">
                        <Minus className="w-3 h-3" />
                      </button>
                      <span className="w-8 text-center font-bold">{l.quantity}</span>
                      <button type="button" onClick={() => updateQty(l.variant_id, 1)} className="w-6 h-6 rounded bg-emerald-100 text-emerald-900 font-bold flex items-center justify-center">
                        <Plus className="w-3 h-3" />
                      </button>
                    </div>
                    <div className="flex items-center gap-1">
                      <input
                        type="number"
                        min={0}
                        value={l.line_discount_dzd || ""}
                        onChange={(e) => setLineDiscount(l.variant_id, e.target.value)}
                        placeholder="Remise"
                        className="w-16 px-1.5 py-1 rounded border border-gray-200 font-mono text-[11px]"
                        title="Remise sur la ligne (DA)"
                      />
                      <span className="font-mono font-bold w-20 text-right">{fmt(l.unit_price_dzd * l.quantity - Math.min(l.line_discount_dzd, l.unit_price_dzd * l.quantity))}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Totals + payment */}
            <div className="p-3 border-t space-y-2">
              <div className="flex justify-between"><span className="text-gray-500">Sous-total</span><span className="font-mono">{fmt(subtotal)}</span></div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Remise globale (DA)</span>
                <input
                  type="number"
                  min={0}
                  value={orderDiscount}
                  onChange={(e) => setOrderDiscount(e.target.value)}
                  placeholder="0"
                  className="w-24 px-2 py-1 rounded border border-gray-200 font-mono text-right"
                />
              </div>
              <div className="flex justify-between text-base font-bold text-[#063D2E]">
                <span>Total</span><span className="font-mono">{fmt(total)}</span>
              </div>

              <div className="grid grid-cols-3 gap-1.5 pt-1">
                {([
                  ["cash", "Espèces", Banknote],
                  ["card", "Carte", CreditCard],
                  ["transfer", "Virement", Wallet],
                ] as [PaymentMethod, string, any][]).map(([m, label, Icon]) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setPayMethod(m)}
                    className={`py-2 rounded-xl border font-bold flex flex-col items-center gap-1 ${payMethod === m ? "bg-[#063D2E] text-[#D4AF62] border-[#063D2E]" : "border-gray-200 text-gray-600"}`}
                  >
                    <Icon className="w-4 h-4" /> {label}
                  </button>
                ))}
              </div>

              {payMethod === "cash" && (
                <div className="flex items-center justify-between pt-1">
                  <span className="text-gray-500">Montant reçu</span>
                  <input
                    type="number"
                    min={0}
                    value={tendered}
                    onChange={(e) => setTendered(e.target.value)}
                    placeholder={String(total)}
                    className="w-28 px-2 py-1 rounded border border-gray-200 font-mono text-right"
                  />
                </div>
              )}
              {payMethod === "cash" && tenderedNum > 0 && (
                <div className="flex justify-between font-bold text-emerald-700">
                  <span>Monnaie à rendre</span><span className="font-mono">{fmt(change)}</span>
                </div>
              )}

              <button
                type="button"
                disabled={busy || cart.length === 0}
                onClick={handleConfirmSale}
                className="w-full py-3 rounded-xl bg-gradient-to-r from-[#D4AF62] to-[#E8D4A5] text-[#02291F] font-extrabold text-sm flex items-center justify-center gap-2 disabled:opacity-50"
              >
                <CheckCircle2 className="w-5 h-5" /> Encaisser {fmt(total)}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* VARIANT PICKER MODAL */}
      {variantPicker && (
        <Modal onClose={() => setVariantPicker(null)} title={variantPicker.name_fr}>
          <div className="flex flex-wrap gap-2">
            {(variantPicker.variants || []).map((v: any) => (
              <button
                key={v.variant_id}
                type="button"
                disabled={v.stock_qty < 1}
                onClick={() => addVariantToCart({ ...v, product_name: variantPicker.name_fr })}
                className="px-3 py-2 rounded-xl border font-bold disabled:opacity-40 hover:bg-[#063D2E] hover:text-[#D4AF62]"
              >
                {v.variant_title} · {fmt(v.unit_price_dzd)} · {v.stock_qty} dispo
              </button>
            ))}
          </div>
        </Modal>
      )}

      {/* CLOSE REGISTER MODAL */}
      {showClose && session && (
        <Modal onClose={() => setShowClose(false)} title="Clôturer la caisse">
          <p className="text-gray-500 mb-3">
            Caisse attendue: <strong>{fmt(session.expected_cash_dzd || 0)}</strong> (fond {fmt(session.opening_float_dzd)} + ventes espèces).
          </p>
          <label className="block font-bold mb-1 text-[#063D2E]">Espèces comptées (DA)</label>
          <input
            type="number"
            min={0}
            value={countedCash}
            onChange={(e) => setCountedCash(e.target.value)}
            className="w-full px-3 py-2 rounded-xl border border-gray-300 font-mono mb-3"
          />
          <button
            type="button"
            disabled={busy}
            onClick={handleCloseRegister}
            className="w-full py-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold disabled:opacity-50"
          >
            Confirmer la clôture
          </button>
        </Modal>
      )}

      {/* REFUND MODAL */}
      {refundTarget && (
        <Modal onClose={() => setRefundTarget(null)} title={`Rembourser ${refundTarget.sale_reference}`}>
          <p className="text-gray-500 mb-3">
            Rembourse l'intégralité des articles encore remboursables de cette vente ({fmt(refundTarget.total_dzd)}). Le stock est réintégré.
          </p>
          <button
            type="button"
            disabled={busy}
            onClick={() => handleFullRefund(refundTarget)}
            className="w-full py-2.5 rounded-xl bg-red-600 text-white font-bold disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <RotateCcw className="w-4 h-4" /> Confirmer le remboursement total
          </button>
        </Modal>
      )}

      {/* RECEIPT MODAL */}
      {receipt && <ReceiptModal sale={receipt} onClose={() => setReceipt(null)} onPrint={printReceipt} />}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Small modal wrapper
// ---------------------------------------------------------------------------
const Modal: React.FC<{ title: string; onClose: () => void; children: React.ReactNode }> = ({ title, onClose, children }) => (
  <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
    <div className="bg-white rounded-2xl p-5 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-serif font-bold text-[#063D2E]">{title}</h3>
        <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-700">
          <X className="w-5 h-5" />
        </button>
      </div>
      {children}
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Receipt
// ---------------------------------------------------------------------------
const ReceiptModal: React.FC<{ sale: any; onClose: () => void; onPrint: () => void }> = ({ sale, onClose, onPrint }) => {
  const b = sale.boutique_info || {};
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
        <div id="pos-receipt" className="p-5 font-mono text-[11px] text-gray-800">
          <div className="text-center mb-2">
            <div className="font-bold text-sm">{b.name || "Mus Luxury"}</div>
            {b.address && <div className="text-[10px]">{b.address}</div>}
            {b.phone && <div className="text-[10px]">Tél: {b.phone}</div>}
          </div>
          <div className="border-t border-dashed my-2" />
          <div>Reçu: {sale.sale_reference}</div>
          <div>{new Date(sale.created_at).toLocaleString("fr-DZ")}</div>
          {sale.cashier_name && <div>Caissier: {sale.cashier_name}</div>}
          {sale.sale_type === "refund" && <div className="font-bold text-red-700">** REMBOURSEMENT **</div>}
          <div className="border-t border-dashed my-2" />
          {(sale.items || []).map((it: any) => (
            <div key={it.id} className="flex justify-between">
              <span className="truncate pr-2">{it.quantity}× {it.product_name} ({it.variant_title})</span>
              <span>{fmt(it.line_total_dzd)}</span>
            </div>
          ))}
          <div className="border-t border-dashed my-2" />
          <div className="flex justify-between"><span>Sous-total</span><span>{fmt(sale.subtotal_dzd)}</span></div>
          {sale.discount_dzd > 0 && <div className="flex justify-between"><span>Remise</span><span>-{fmt(sale.discount_dzd)}</span></div>}
          {sale.tax_dzd > 0 && <div className="flex justify-between"><span>Taxe</span><span>{fmt(sale.tax_dzd)}</span></div>}
          <div className="flex justify-between font-bold text-sm"><span>TOTAL</span><span>{fmt(sale.total_dzd)}</span></div>
          <div className="border-t border-dashed my-2" />
          {(sale.payments || []).map((p: any) => (
            <div key={p.id} className="flex justify-between">
              <span>{p.method === "cash" ? "Espèces" : p.method === "card" ? "Carte" : p.method === "transfer" ? "Virement" : p.method}</span>
              <span>{fmt(p.amount_dzd)}</span>
            </div>
          ))}
          {(sale.payments || []).some((p: any) => p.change_dzd > 0) && (
            <div className="flex justify-between"><span>Monnaie</span><span>{fmt((sale.payments || []).reduce((s: number, p: any) => s + (p.change_dzd || 0), 0))}</span></div>
          )}
          <div className="text-center mt-3 text-[10px]">Merci de votre visite — {b.name || "Mus Luxury"}</div>
        </div>
        <div className="p-3 border-t flex gap-2 print:hidden">
          <button type="button" onClick={onPrint} className="flex-1 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center justify-center gap-2">
            <Printer className="w-4 h-4" /> Imprimer
          </button>
          <button type="button" onClick={onClose} className="flex-1 py-2 rounded-xl bg-gray-100 font-bold">
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};
