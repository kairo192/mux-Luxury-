import React, { useCallback, useEffect, useRef, useState } from "react";
import { Plus, Search, ScanLine, Barcode, Printer, PackagePlus, Pencil, Globe, Store, RefreshCw, CheckCircle2, AlertTriangle, X, Layers } from "lucide-react";
import { DesktopCmsApi, mediaUrl, PLACEHOLDER_IMG } from "../api/adminClient";
import { useBarcodeScanner } from "../utils/useBarcodeScanner";
import { confirmClientAction } from "../utils/clientNotifier";
import { printLabelItems } from "../utils/labelPrint";
import { pickLang, tr } from "../i18n/translations";
import { useT } from "../i18n";
import { QuickAddPanel, SINGLE, variantName, type StoreItem, type StoreVariant } from "../components/shop/QuickAddPanel";
import { LabelsDialog } from "../components/shop/LabelsDialog";

type Show = "all" | "store" | "online" | "no_barcode" | "low";
const SHOWS: Show[] = ["all", "store", "online", "no_barcode", "low"];
const PAGE = 30;
const fmt = (n: number) => `${Math.round(n || 0).toLocaleString("fr-FR").replace(/ | /g, " ")} DA`;
const looksLikeBarcode = (s: string) => /^[0-9]{8,14}$/.test(s) || /^[A-Z0-9-]{6,}$/.test(s);

/**
 * Shop items — the articles of the physical shop, made quick: add one with its
 * colours / sizes and quantities, give each one a barcode (scanned or created),
 * print a label per piece, record new arrivals. Same products / stock as the
 * rest of the CMS: the till sells them by scanning; "shop only" ones are
 * hidden from the online shop.
 */
export const ShopItemsPage: React.FC<{ onCatalogChanged?: () => void }> = ({ onCatalogChanged }) => {
  useT(); // re-render on language change
  const [items, setItems] = useState<StoreItem[]>([]);
  const [total, setTotal] = useState(0);
  const [missing, setMissing] = useState(0);
  const [storeName, setStoreName] = useState("Mus Luxury");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [show, setShow] = useState<Show>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [adding, setAdding] = useState<{ existing?: StoreItem | null; barcode?: string } | null>(null);
  const [labelsFor, setLabelsFor] = useState<{ item: StoreItem; only?: number | null } | null>(null);
  const [editing, setEditing] = useState<StoreItem | null>(null);
  const [notFound, setNotFound] = useState<string | null>(null);
  const [receive, setReceive] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const shown = useRef(0); // items on screen, for "show more"
  shown.current = items.length;

  const flash = (msg: string, ok = true) => {
    if (ok) { setSuccess(msg); setError(null); setTimeout(() => setSuccess(null), 6000); } else { setError(msg); setSuccess(null); }
  };

  const load = useCallback(async (append = false) => {
    setLoading(true);
    try {
      const r = await DesktopCmsApi.listStoreItems({ q: query, show, limit: PAGE, offset: append ? shown.current : 0 });
      setItems((cur) => (append ? [...cur, ...r.items.filter((n: StoreItem) => !cur.some((c) => c.id === n.id))] : r.items));
      setTotal(r.total);
      setMissing(r.missing_barcodes);
      if (r.store_name) setStoreName(r.store_name);
      const exact = query && r.items.length === 0 && looksLikeBarcode(query);
      setNotFound(exact ? query : null);
    } catch (e: any) {
      flash(e?.userMessage || tr("status.error"), false);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, show]);

  useEffect(() => { load(false); }, [load]);

  // A scan anywhere on the screen searches that code (the quick-add form
  // takes scans in its own barcode fields).
  useBarcodeScanner((code) => { setQ(code); setQuery(code); }, { enabled: !adding && !labelsFor && !editing });

  const replace = (item: StoreItem) => {
    setItems((cur) => (cur.some((i) => i.id === item.id) ? cur.map((i) => (i.id === item.id ? item : i)) : [item, ...cur]));
    onCatalogChanged?.();
  };

  const saved = async (item: StoreItem, toPrint: Array<{ variant: StoreVariant; copies: number }> | null) => {
    const wasNew = !adding?.existing;
    setAdding(null);
    setNotFound(null);
    replace(item);
    load(false);
    let msg = wasNew ? tr("shop.added", { name: item.name_fr, n: item.variants.length }) : tr("shop.variants_added", { name: item.name_fr });
    if (toPrint && toPrint.some((p) => p.copies > 0)) {
      const r = await printLabelItems(toPrint.map(({ variant, copies }) => ({
        store_name: storeName, product_name: item.name_fr, variant_title: variant.title === SINGLE ? "" : variant.title,
        sku: variant.sku, price_dzd: variant.price_dzd, barcode: variant.barcode || "", symbology: variant.symbology, copies,
      })));
      const n = toPrint.reduce((s, p) => s + Math.min(100, p.copies), 0);
      if (!r.ok) return flash(`${msg} ${r.error || tr("hw.label_error")}`, false);
      msg += " " + (r.via === "printer" ? tr("shop.printed_n", { n }) : tr("shop.print_dialog", { n }));
    }
    flash(msg);
    searchRef.current?.focus();
  };

  const doReceive = async (item: StoreItem, v: StoreVariant) => {
    const n = parseInt(receive[v.id] || "0", 10);
    if (!(n > 0)) return;
    setBusy(v.id);
    try {
      const r = await DesktopCmsApi.receiveStoreStock(v.id, n);
      replace(r.item);
      setReceive({ ...receive, [v.id]: "" });
      const print = await confirmClientAction({
        title: tr("shop.received_title"),
        message: tr("shop.received_question", { n, title: `${item.name_fr} — ${v.title}`, total: r.new_qty }),
        confirmLabel: tr("shop.print_n", { n }),
        cancelLabel: tr("shop.no_labels"),
      });
      if (print) {
        const fresh = r.item.variants.find((x: StoreVariant) => x.id === v.id) || v;
        const p = await printLabelItems([{ store_name: storeName, product_name: item.name_fr, variant_title: fresh.title === SINGLE ? "" : fresh.title,
          sku: fresh.sku, price_dzd: fresh.price_dzd, barcode: fresh.barcode || "", symbology: fresh.symbology, copies: n }]);
        if (!p.ok) return flash(p.error || tr("hw.label_error"), false);
      }
      flash(tr("shop.received", { n, title: v.title, total: r.new_qty }));
    } catch (e: any) {
      flash(e?.userMessage || tr("status.error"), false);
    } finally {
      setBusy(null);
    }
  };

  const generateAll = async () => {
    try {
      const r = await DesktopCmsApi.generateAllMissingBarcodes();
      flash(tr("shop.generated_n", { n: r.generated }));
      load(false);
    } catch (e: any) {
      flash(e?.userMessage || tr("status.error"), false);
    }
  };

  const generateFor = async (item: StoreItem) => {
    setBusy(-item.id);
    try {
      const r = await DesktopCmsApi.generateStoreBarcodes(item.id);
      replace(r.item);
      flash(tr("shop.generated_n", { n: r.generated }));
    } catch (e: any) {
      flash(e?.userMessage || tr("status.error"), false);
    } finally {
      setBusy(null);
    }
  };

  const showLabel: Record<Show, string> = {
    all: tr("shop.show_all"), store: tr("shop.show_store"), online: tr("shop.show_online"),
    no_barcode: tr("shop.show_no_barcode"), low: tr("shop.show_low"),
  };

  return (
    <div className="space-y-4 text-sm">
      {error && (
        <div role="alert" className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" /> <span data-testid="shop-error">{error}</span>
          <button aria-label={tr("ui.close")} type="button" onClick={() => setError(null)} className="ms-auto"><X className="w-4 h-4" /></button>
        </div>
      )}
      {success && (
        <div role="status" className="p-4 rounded-2xl bg-emerald-50 border-2 border-emerald-200 text-emerald-800 font-bold flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 shrink-0" /> <span data-testid="shop-success">{success}</span>
        </div>
      )}

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2"><Store className="w-5 h-5" /> {tr("shop.title")}</h3>
            <p className="text-gray-500 mt-1 max-w-3xl">{tr("shop.subtitle")}</p>
          </div>
          <div className="flex gap-2">
            {missing > 0 && (
              <button type="button" onClick={generateAll} className="h-12 px-4 rounded-2xl border-2 border-amber-300 text-amber-800 font-bold flex items-center gap-2 active:scale-95">
                <Barcode className="w-5 h-5" /> {tr("shop.generate_all", { n: missing })}
              </button>
            )}
            <button type="button" onClick={() => setAdding({})} className="h-12 px-5 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
              <Plus className="w-5 h-5" /> {tr("shop.new")}
            </button>
          </div>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); }} className="flex gap-2">
          <div className="relative flex-1">
            <ScanLine className="w-5 h-5 text-gray-400 absolute top-3.5 start-3" />
            <input ref={searchRef} value={q} onChange={(e) => { setQ(e.target.value); if (!e.target.value) setQuery(""); }} data-barcode-target="true"
              aria-label={tr("shop.search")} placeholder={tr("shop.search_ph")} className="w-full h-12 ps-10 pe-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none" />
          </div>
          <button type="submit" aria-label={tr("shop.search")} className="h-12 w-12 rounded-2xl bg-[#063D2E] text-[#D4AF62] flex items-center justify-center active:scale-95"><Search className="w-5 h-5" /></button>
        </form>

        <div className="flex flex-wrap gap-2" role="tablist">
          {SHOWS.map((s) => (
            <button key={s} type="button" role="tab" aria-selected={show === s} onClick={() => setShow(s)}
              className={`h-9 px-3 rounded-xl font-bold text-xs active:scale-95 ${show === s ? "bg-[#063D2E] text-[#D4AF62]" : "bg-gray-100 text-gray-600"}`}>
              {showLabel[s]}{s === "no_barcode" && missing > 0 ? ` (${missing})` : ""}
            </button>
          ))}
          <span className="ms-auto text-gray-500 self-center">{tr("shop.count", { n: total })}</span>
        </div>
      </div>

      {notFound && (
        <div className="p-4 rounded-2xl bg-amber-50 border-2 border-amber-200 text-amber-900 flex flex-wrap items-center justify-between gap-3">
          <span>{tr("shop.not_found", { code: notFound })}</span>
          <button type="button" onClick={() => setAdding({ barcode: notFound })} className="h-11 px-4 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
            <Plus className="w-5 h-5" /> {tr("shop.new_with_code")}
          </button>
        </div>
      )}

      {!loading && items.length === 0 && !notFound && (
        <div className="bg-white p-10 rounded-3xl border border-gray-200 text-center text-gray-400">{query || show !== "all" ? tr("shop.none_found") : tr("shop.empty")}</div>
      )}

      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.id} data-testid="shop-item" data-item-name={item.name_fr} className="bg-white p-4 rounded-3xl border border-gray-200">
            <div className="flex flex-wrap items-start gap-3">
              <img src={item.main_image_url ? mediaUrl(item.main_image_url) : PLACEHOLDER_IMG} alt="" className="w-14 h-14 rounded-2xl object-cover bg-gray-100" />
              <div className="flex-1 min-w-[200px]">
                <div className="font-bold text-[#063D2E] text-base flex flex-wrap items-center gap-2">
                  {pickLang(item, "name")}
                  {item.sold_online
                    ? <span className="inline-flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded bg-sky-100 text-sky-800"><Globe className="w-3 h-3" /> {tr("shop.badge_online")}</span>
                    : <span className="inline-flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#D4AF62]/20 text-[#7a5c16]"><Store className="w-3 h-3" /> {tr("shop.badge_store")}</span>}
                  {item.status === "draft" && <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-gray-200 text-gray-600">{tr("shop.badge_draft")}</span>}
                </div>
                <div className="text-gray-500 text-[11px]">{pickLang({ category_fr: item.category_fr, category_ar: item.category_ar, category_en: item.category_en }, "category")} · {item.sku} · <span dir="ltr">{fmt(item.selling_price_dzd)}</span></div>
              </div>
              <div className="text-end">
                <div className="font-mono font-bold text-[#063D2E] text-lg">{item.total_stock}</div>
                <div className="text-[11px] text-gray-500">{tr("shop.pieces")}</div>
              </div>
            </div>

            <div className="mt-3 overflow-x-auto">
              <table className="w-full">
                <thead className="text-[11px] uppercase text-gray-500"><tr>
                  <th className="text-start py-1">{tr("shop.th_variant")}</th><th className="text-start py-1">{tr("shop.th_barcode")}</th>
                  <th className="text-start py-1">{tr("shop.th_price")}</th><th className="text-start py-1">{tr("shop.th_stock")}</th>
                  <th className="text-start py-1">{tr("shop.th_arrival")}</th><th />
                </tr></thead>
                <tbody>
                  {item.variants.filter((v) => v.is_active).map((v) => (
                    <tr key={v.id} data-testid="shop-variant" data-variant-title={v.title} className="border-t border-gray-100">
                      <td className="py-2 font-bold text-[#063D2E]">{variantName(v.title)}</td>
                      <td className="py-2 font-mono text-xs" data-testid="variant-barcode">{v.barcode || <span className="text-amber-700 font-sans font-bold">{tr("shop.no_barcode")}</span>}</td>
                      <td className="py-2 font-mono"><span dir="ltr">{fmt(v.price_dzd)}</span></td>
                      <td className={`py-2 font-mono font-bold ${v.stock_qty <= v.low_stock_threshold ? "text-red-600" : ""}`} data-testid="variant-stock">{v.stock_qty}</td>
                      <td className="py-2">
                        <form onSubmit={(e) => { e.preventDefault(); doReceive(item, v); }} className="flex items-center gap-1">
                          <input aria-label={tr("shop.arrival_of", { title: v.title })} inputMode="numeric" value={receive[v.id] || ""} placeholder="+"
                            onChange={(e) => setReceive({ ...receive, [v.id]: e.target.value.replace(/[^\d]/g, "").slice(0, 5) })}
                            className="w-16 h-9 px-2 rounded-xl border-2 border-gray-200 font-mono" />
                          <button type="submit" disabled={busy === v.id || !(parseInt(receive[v.id] || "0", 10) > 0)} aria-label={tr("shop.add_arrival", { title: v.title })}
                            className="h-9 w-9 rounded-xl bg-emerald-600 text-white flex items-center justify-center disabled:opacity-30 active:scale-95"><PackagePlus className="w-4 h-4" /></button>
                        </form>
                      </td>
                      <td className="py-2 text-end">
                        <button type="button" disabled={!v.barcode} onClick={() => setLabelsFor({ item, only: v.id })} aria-label={tr("shop.labels_of", { title: v.title })}
                          className="h-9 w-9 rounded-xl border-2 border-gray-200 inline-flex items-center justify-center text-gray-600 disabled:opacity-30 active:scale-95"><Printer className="w-4 h-4" /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap gap-1.5 mt-3">
              <button type="button" onClick={() => setLabelsFor({ item })} className="h-10 px-3 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-1.5 active:scale-95">
                <Printer className="w-4 h-4" /> {tr("shop.labels")}
              </button>
              {item.missing_barcodes > 0 && (
                <button type="button" disabled={busy === -item.id} onClick={() => generateFor(item)} className="h-10 px-3 rounded-xl border-2 border-amber-300 text-amber-800 font-bold flex items-center gap-1.5 active:scale-95">
                  <Barcode className="w-4 h-4" /> {tr("shop.generate_n", { n: item.missing_barcodes })}
                </button>
              )}
              <button type="button" onClick={() => setAdding({ existing: item })} className="h-10 px-3 rounded-xl border-2 border-gray-200 font-bold flex items-center gap-1.5 active:scale-95">
                <Layers className="w-4 h-4" /> {tr("shop.add_variants")}
              </button>
              <button type="button" onClick={() => setEditing(item)} className="h-10 px-3 rounded-xl border-2 border-gray-200 font-bold flex items-center gap-1.5 active:scale-95">
                <Pencil className="w-4 h-4" /> {tr("shop.edit")}
              </button>
            </div>
          </div>
        ))}
      </div>

      {items.length < total && (
        <button type="button" onClick={() => load(true)} disabled={loading} className="w-full h-12 rounded-2xl border-2 border-gray-200 font-bold text-gray-600 flex items-center justify-center gap-2">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> {tr("shop.more", { n: total - items.length })}
        </button>
      )}

      {adding && <QuickAddPanel existing={adding.existing} prefillBarcode={adding.barcode} onSaved={saved} onClose={() => setAdding(null)} />}
      {labelsFor && (
        <LabelsDialog item={labelsFor.item} only={labelsFor.only} storeName={storeName} onClose={() => setLabelsFor(null)}
          onChanged={(it) => { replace(it); setLabelsFor({ ...labelsFor, item: it }); }} onDone={(m, ok) => flash(m, ok)} />
      )}
      {editing && <EditDialog item={editing} onClose={() => setEditing(null)} onSaved={(it) => { replace(it); setEditing(null); flash(tr("common.saved")); }} />}
    </div>
  );
};

/** Name, price, cost and where it is sold. Everything else: Products screen. */
function EditDialog({ item, onClose, onSaved }: { item: StoreItem; onClose: () => void; onSaved: (i: StoreItem) => void }) {
  const [name, setName] = useState(item.name_fr);
  const [price, setPrice] = useState(String(item.selling_price_dzd));
  const [cost, setCost] = useState(String(item.purchase_cost_dzd || ""));
  const [online, setOnline] = useState(item.sold_online);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setError(null);
    if (!name.trim()) return setError(tr("shop.need_name"));
    if (price.trim() === "") return setError(tr("shop.need_price"));
    setBusy(true);
    try {
      onSaved(await DesktopCmsApi.editStoreItem(item.id, {
        name: name.trim(), price_dzd: Number(price), cost_dzd: cost.trim() === "" ? undefined : Number(cost),
        sold_online: online !== item.sold_online ? online : undefined,
      }));
    } catch (e: any) {
      setError(e?.userMessage || tr("status.error"));
    } finally {
      setBusy(false);
    }
  };
  const input = "w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none";
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="shop-edit-title" className="bg-white rounded-3xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <h3 id="shop-edit-title" className="font-serif font-bold text-[#063D2E] text-lg">{tr("shop.edit_title")}</h3>
          <button aria-label={tr("ui.close")} type="button" onClick={onClose} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100"><X className="w-6 h-6" /></button>
        </div>
        <div className="p-5 space-y-3 text-sm">
          {error && <div role="alert" className="p-3 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold">{error}</div>}
          <label className="block"><span className="block font-bold text-[#063D2E] mb-1 text-xs uppercase">{tr("shop.f_name")}</span><input value={name} onChange={(e) => setName(e.target.value)} className={input} /></label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block"><span className="block font-bold text-[#063D2E] mb-1 text-xs uppercase">{tr("shop.f_price")}</span><input inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value.replace(/[^\d]/g, ""))} className={`${input} font-mono`} /></label>
            <label className="block"><span className="block font-bold text-[#063D2E] mb-1 text-xs uppercase">{tr("shop.f_cost")}</span><input inputMode="numeric" value={cost} onChange={(e) => setCost(e.target.value.replace(/[^\d]/g, ""))} className={`${input} font-mono`} /></label>
          </div>
          <label className="flex items-start gap-3 p-3 rounded-2xl border-2 border-gray-100 cursor-pointer">
            <input type="checkbox" checked={online} onChange={(e) => setOnline(e.target.checked)} className="w-5 h-5 mt-0.5" />
            <span><span className="font-bold text-[#063D2E] block">{tr("shop.also_online")}</span><span className="text-gray-500 text-xs">{tr("shop.also_online_hint")}</span></span>
          </label>
          <p className="text-[11px] text-gray-500">{tr("shop.edit_more")}</p>
          <button type="button" disabled={busy} onClick={save} className="w-full h-12 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold disabled:opacity-50">{tr("shop.save")}</button>
        </div>
      </div>
    </div>
  );
}
