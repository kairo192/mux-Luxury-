import { useEffect, useMemo, useRef, useState } from "react";
import { X, Plus, Save, Printer, ImagePlus, ScanLine, Trash2 } from "lucide-react";
import { DesktopCmsApi, mediaUrl } from "../../api/adminClient";
import { useEscapeToClose } from "../../utils/useEscapeToClose";
import { pickLang, tr } from "../../i18n/translations";

export interface StoreVariant {
  id: number;
  sku: string;
  barcode: string | null;
  symbology: string | null;
  title: string;
  price_dzd: number;
  stock_qty: number;
  is_active: boolean;
  low_stock_threshold: number;
}

export interface StoreItem {
  id: number;
  sku: string;
  name_fr: string;
  name_ar?: string;
  name_en?: string;
  selling_price_dzd: number;
  purchase_cost_dzd: number;
  main_image_url: string | null;
  status: string;
  sales_channel: "all" | "store";
  sold_online: boolean;
  category_id: number;
  category_fr?: string;
  category_ar?: string;
  category_en?: string;
  variants: StoreVariant[];
  total_stock: number;
  missing_barcodes: number;
}

interface AxisOption { value: string; label_fr?: string; label_ar?: string; label_en?: string; color_hex?: string | null }
interface Axis { attr_key: string; label_fr: string; label_ar?: string; label_en?: string; options: AxisOption[] }
interface Category { id: number; name_fr: string; name_ar?: string; name_en?: string; axes: Axis[] }

interface Row { key: string; attributes: Record<string, string>; title: string; quantity: string; barcode: string; price: string }

const LAST_CATEGORY = "luxe_shop_last_category";
const NO_AXES: Axis[] = [];

/** All combinations of the chosen values (colour × size …). */
function combos(axes: Axis[], chosen: Record<string, string[]>): Array<Record<string, string>> {
  const used = axes.filter((a) => (chosen[a.attr_key] || []).length);
  let out: Array<Record<string, string>> = [{}];
  for (const a of used) out = out.flatMap((c) => chosen[a.attr_key].map((v) => ({ ...c, [a.attr_key]: v })));
  return used.length ? out : [];
}

/** The server names a one-piece article "Unique": show it in the CMS language. */
export const SINGLE = "Unique";
export const variantName = (title: string) => (title === SINGLE ? tr("shop.single") : title);


/**
 * Quick add of a shop article (or of new colours / sizes for one already
 * there, with `existing`). One row per colour / size: how many pieces, and the
 * barcode — scanned from the article's own label, or left empty so the shop
 * creates one.
 */
export function QuickAddPanel({ existing, prefillBarcode, onSaved, onClose }: {
  existing?: StoreItem | null;
  prefillBarcode?: string;
  onSaved: (item: StoreItem, print: Array<{ variant: StoreVariant; copies: number }> | null) => void;
  onClose: () => void;
}) {
  useEscapeToClose(onClose, true);
  const [categories, setCategories] = useState<Category[]>([]);
  const [name, setName] = useState("");
  const [categoryId, setCategoryId] = useState<number | "">(existing?.category_id ?? (Number(localStorage.getItem(LAST_CATEGORY)) || ""));
  const [price, setPrice] = useState("");
  const [cost, setCost] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [uploading, setUploading] = useState(false);
  const [online, setOnline] = useState(false);
  const [chosen, setChosen] = useState<Record<string, string[]>>({});
  const [newValue, setNewValue] = useState<Record<string, string>>({});
  const [models, setModels] = useState<string[]>([]);
  const [modelInput, setModelInput] = useState("");
  const [rows, setRows] = useState<Record<string, Row>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    DesktopCmsApi.listCategories(false).then((res: any) => {
      const list = (Array.isArray(res) ? res : res?.items || []).map((c: any) => ({
        id: c.id, name_fr: c.name_fr, name_ar: c.name_ar, name_en: c.name_en,
        axes: (c.attributes || []).filter((a: any) => a.is_variant_axis).map((a: any) => ({
          attr_key: a.attr_key, label_fr: a.label_fr, label_ar: a.label_ar, label_en: a.label_en, options: a.options || [],
        })),
      }));
      setCategories(list);
      setCategoryId((cur) => (cur && list.some((c: Category) => c.id === cur) ? cur : list[0]?.id ?? ""));
    }).catch((e: any) => setError(e?.userMessage || tr("status.error")));
    nameRef.current?.focus();
  }, []);

  const category = categories.find((c) => c.id === categoryId);
  const axes = category?.axes ?? NO_AXES;

  // Rows follow the chosen values; what was typed in a row is kept.
  const wanted = useMemo(() => {
    const label = (key: string, value: string) => {
      const o = axes.find((a) => a.attr_key === key)?.options.find((x) => x.value === value);
      return (o && (o.label_fr || "").trim()) || value;
    };
    const list = combos(axes, chosen).map((attrs) => ({
      key: JSON.stringify(attrs), attributes: attrs,
      title: Object.keys(attrs).sort().map((k) => label(k, attrs[k])).join(" / "),
    }));
    if (list.length) return list;
    if (models.length) return models.map((m) => ({ key: `model:${m}`, attributes: {}, title: m }));
    return existing ? [] : [{ key: "single", attributes: {}, title: tr("shop.single") }];
  }, [axes, chosen, models, existing]);

  useEffect(() => {
    setRows((prev) => {
      const next: Record<string, Row> = {};
      wanted.forEach((w, i) => {
        next[w.key] = prev[w.key] || { ...w, quantity: "1", barcode: i === 0 && prefillBarcode ? prefillBarcode : "", price: "" };
      });
      return next;
    });
  }, [wanted, prefillBarcode]);

  const toggle = (key: string, value: string) =>
    setChosen((c) => ({ ...c, [key]: (c[key] || []).includes(value) ? c[key].filter((v) => v !== value) : [...(c[key] || []), value] }));

  const addValue = (axis: Axis) => {
    const v = (newValue[axis.attr_key] || "").trim();
    if (!v) return;
    if (!axis.options.some((o) => o.value.toLowerCase() === v.toLowerCase())) axis.options.push({ value: v, label_fr: v });
    const value = axis.options.find((o) => o.value.toLowerCase() === v.toLowerCase())!.value;
    setChosen((c) => ({ ...c, [axis.attr_key]: (c[axis.attr_key] || []).includes(value) ? c[axis.attr_key] : [...(c[axis.attr_key] || []), value] }));
    setNewValue((n) => ({ ...n, [axis.attr_key]: "" }));
  };

  const addModel = () => {
    const m = modelInput.trim();
    if (m && !models.includes(m)) setModels([...models, m]);
    setModelInput("");
  };

  const upload = async (f: File | undefined) => {
    if (!f) return;
    setUploading(true);
    try {
      const r: any = await DesktopCmsApi.uploadMediaFile(f);
      setImageUrl(r?.url || r?.path || "");
    } catch (e: any) {
      setError(e?.userMessage || tr("status.error"));
    } finally {
      setUploading(false);
    }
  };

  const list = wanted.map((w) => rows[w.key]).filter(Boolean);
  const pieces = list.reduce((n, r) => n + (parseInt(r.quantity || "0", 10) || 0), 0);

  const save = async (print: boolean) => {
    setError(null);
    if (!existing) {
      if (!name.trim()) return setError(tr("shop.need_name"));
      if (!categoryId) return setError(tr("shop.need_category"));
      if (price.trim() === "" || !(Number(price) >= 0)) return setError(tr("shop.need_price"));
    }
    if (!list.length) return setError(tr("shop.need_variant"));
    const bad = list.find((r) => !(parseInt(r.quantity || "0", 10) >= 0));
    if (bad) return setError(tr("shop.need_quantity", { title: bad.title }));
    const variants = list.map((r) => ({
      attributes: r.attributes,
      title: Object.keys(r.attributes).length || r.key === "single" ? undefined : r.title,
      quantity: parseInt(r.quantity || "0", 10) || 0,
      barcode: r.barcode.trim() || undefined,
      price_dzd: r.price.trim() ? Number(r.price) : undefined,
    }));
    setBusy(true);
    try {
      const item: StoreItem = existing
        ? await DesktopCmsApi.addStoreVariants(existing.id, variants)
        : await DesktopCmsApi.quickAddStoreItem({
          name: name.trim(), category_id: categoryId, price_dzd: Number(price), cost_dzd: Number(cost) || 0,
          image_url: imageUrl || undefined, sold_online: online, variants,
        });
      if (!existing && categoryId) localStorage.setItem(LAST_CATEGORY, String(categoryId));
      // The server creates the rows in this order, after any variant already there.
      const made = item.variants.slice(-list.length);
      const toPrint = print
        ? made.map((v, i) => ({ variant: v, copies: parseInt(list[i]?.quantity || "0", 10) || 0 }))
        : null;
      onSaved(item, toPrint);
    } catch (e: any) {
      setError(e?.userMessage || tr("status.error"));
    } finally {
      setBusy(false);
    }
  };

  const input = "w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none";
  const label = "block font-bold text-[#063D2E] mb-1 text-xs uppercase tracking-wide";
  const optionLabel = (o: AxisOption) => pickLang(o, "label") || o.value;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="quick-add-title" className="bg-white rounded-3xl w-full max-w-4xl max-h-[94vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b sticky top-0 bg-white z-10">
          <h3 id="quick-add-title" className="font-serif font-bold text-[#063D2E] text-lg">
            {existing ? tr("shop.add_variants_title", { name: pickLang(existing, "name") }) : tr("shop.new_title")}
          </h3>
          <button aria-label={tr("ui.close")} type="button" onClick={onClose} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95"><X className="w-6 h-6" /></button>
        </div>

        <div className="p-5 space-y-5 text-sm">
          {error && <div role="alert" className="p-3 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold">{error}</div>}

          {!existing && (
            <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
              <label className="md:col-span-3">
                <span className={label}>{tr("shop.f_name")}</span>
                <input ref={nameRef} value={name} onChange={(e) => setName(e.target.value)} className={input} placeholder={tr("shop.f_name_ph")} />
              </label>
              <label className="md:col-span-3">
                <span className={label}>{tr("shop.f_category")}</span>
                <select value={categoryId} onChange={(e) => { setCategoryId(Number(e.target.value)); setChosen({}); setModels([]); }} className={`${input} bg-white`}>
                  {categories.map((c) => <option key={c.id} value={c.id}>{pickLang(c, "name")}</option>)}
                </select>
              </label>
              <label className="md:col-span-2">
                <span className={label}>{tr("shop.f_price")}</span>
                <input inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value.replace(/[^\d]/g, ""))} className={`${input} font-mono`} placeholder="9000" />
              </label>
              <label className="md:col-span-2">
                <span className={label}>{tr("shop.f_cost")}</span>
                <input inputMode="numeric" value={cost} onChange={(e) => setCost(e.target.value.replace(/[^\d]/g, ""))} className={`${input} font-mono`} placeholder={tr("shop.optional")} />
              </label>
              <div className="md:col-span-2">
                <span className={label}>{tr("shop.f_photo")}</span>
                <label className={`${input} flex items-center gap-2 cursor-pointer text-gray-500`}>
                  {imageUrl ? <img src={mediaUrl(imageUrl)} alt="" className="w-8 h-8 rounded object-cover" /> : <ImagePlus className="w-5 h-5" />}
                  <span className="truncate">{uploading ? tr("status.loading") : imageUrl ? tr("shop.photo_ok") : tr("shop.optional")}</span>
                  <input type="file" accept="image/*" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
                </label>
              </div>
            </div>
          )}

          {/* colours / sizes */}
          {axes.length > 0 ? axes.map((a) => (
            <div key={a.attr_key}>
              <span className={label}>{pickLang(a, "label")}</span>
              <div className="flex flex-wrap gap-2 items-center">
                {a.options.map((o) => {
                  const on = (chosen[a.attr_key] || []).includes(o.value);
                  return (
                    <button key={o.value} type="button" aria-pressed={on} onClick={() => toggle(a.attr_key, o.value)}
                      className={`h-10 px-3 rounded-xl border-2 font-bold flex items-center gap-1.5 active:scale-95 ${on ? "bg-[#063D2E] text-[#D4AF62] border-[#063D2E]" : "border-gray-200 text-gray-600"}`}>
                      {o.color_hex && <span className="w-4 h-4 rounded-full border border-gray-300" style={{ background: o.color_hex }} />}
                      {optionLabel(o)}
                    </button>
                  );
                })}
                <span className="flex items-center gap-1">
                  <input value={newValue[a.attr_key] || ""} onChange={(e) => setNewValue({ ...newValue, [a.attr_key]: e.target.value })}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addValue(a); } }}
                    aria-label={tr("shop.new_value", { axis: pickLang(a, "label") })} placeholder={tr("shop.new_value_ph")}
                    className="h-10 w-32 px-2 rounded-xl border-2 border-dashed border-gray-300" />
                  <button type="button" onClick={() => addValue(a)} aria-label={tr("shop.add_value")} className="h-10 w-10 rounded-xl border-2 border-gray-200 flex items-center justify-center active:scale-95"><Plus className="w-4 h-4" /></button>
                </span>
              </div>
            </div>
          )) : (
            <div>
              <span className={label}>{tr("shop.models")}</span>
              <div className="flex flex-wrap gap-2 items-center">
                {models.map((m) => (
                  <span key={m} className="h-10 px-3 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-1.5">
                    {m}<button type="button" aria-label={`${tr("misc.delete")} ${m}`} onClick={() => setModels(models.filter((x) => x !== m))}><X className="w-4 h-4" /></button>
                  </span>
                ))}
                <input value={modelInput} onChange={(e) => setModelInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addModel(); } }}
                  aria-label={tr("shop.models")} placeholder={tr("shop.models_ph")} className="h-10 w-48 px-2 rounded-xl border-2 border-dashed border-gray-300" />
                <button type="button" onClick={addModel} aria-label={tr("shop.add_value")} className="h-10 w-10 rounded-xl border-2 border-gray-200 flex items-center justify-center active:scale-95"><Plus className="w-4 h-4" /></button>
              </div>
              <p className="text-[11px] text-gray-500 mt-1">{tr("shop.models_hint")}</p>
            </div>
          )}

          {/* one row per colour / size */}
          {list.length > 0 && (
            <div className="rounded-2xl border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-[#F5F3EE] text-[11px] uppercase text-gray-500">
                  <tr>
                    <th className="text-start px-3 py-2">{tr("shop.th_variant")}</th>
                    <th className="text-start px-3 py-2 w-24">{tr("shop.th_qty")}</th>
                    <th className="text-start px-3 py-2">{tr("shop.th_barcode")}</th>
                    <th className="text-start px-3 py-2 w-32">{tr("shop.th_price")}</th>
                    {axes.length === 0 && models.length > 0 && <th className="w-10" />}
                  </tr>
                </thead>
                <tbody>
                  {list.map((r) => (
                    <tr key={r.key} data-testid="quick-row" className="border-t border-gray-100">
                      <td className="px-3 py-2 font-bold text-[#063D2E]">{r.title}</td>
                      <td className="px-3 py-2">
                        <input aria-label={tr("shop.qty_of", { title: r.title })} inputMode="numeric" value={r.quantity}
                          onChange={(e) => setRows({ ...rows, [r.key]: { ...r, quantity: e.target.value.replace(/[^\d]/g, "") } })}
                          className="w-20 h-10 px-2 rounded-xl border-2 border-gray-200 font-mono" />
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1.5">
                          <ScanLine className="w-4 h-4 text-gray-400 shrink-0" />
                          <input aria-label={tr("shop.barcode_of", { title: r.title })} value={r.barcode} data-barcode-target="true"
                            onChange={(e) => setRows({ ...rows, [r.key]: { ...r, barcode: e.target.value.trim() } })}
                            onKeyDown={(e) => { if (e.key === "Enter") e.preventDefault(); }}
                            placeholder={tr("shop.barcode_ph")} className="w-full h-10 px-2 rounded-xl border-2 border-gray-200 font-mono text-xs" />
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <input aria-label={tr("shop.price_of", { title: r.title })} inputMode="numeric" value={r.price}
                          onChange={(e) => setRows({ ...rows, [r.key]: { ...r, price: e.target.value.replace(/[^\d]/g, "") } })}
                          placeholder={existing ? String(existing.selling_price_dzd) : price || "—"} className="w-28 h-10 px-2 rounded-xl border-2 border-gray-200 font-mono" />
                      </td>
                      {axes.length === 0 && models.length > 0 && (
                        <td className="px-2"><button type="button" aria-label={`${tr("misc.delete")} ${r.title}`} onClick={() => setModels(models.filter((m) => m !== r.title))} className="text-red-500"><Trash2 className="w-4 h-4" /></button></td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="px-3 py-2 text-[11px] text-gray-500 bg-[#FCFBF8]">{tr("shop.barcode_hint")}</p>
            </div>
          )}

          {!existing && (
            <label className="flex items-start gap-3 p-3 rounded-2xl border-2 border-gray-100 cursor-pointer">
              <input type="checkbox" checked={online} onChange={(e) => setOnline(e.target.checked)} className="w-5 h-5 mt-0.5" />
              <span>
                <span className="font-bold text-[#063D2E] block">{tr("shop.also_online")}</span>
                <span className="text-gray-500 text-xs">{tr("shop.also_online_hint")}</span>
              </span>
            </label>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <span className="text-gray-500" data-testid="quick-summary">{tr("shop.summary", { v: list.length, n: pieces })}</span>
            <div className="flex gap-2">
              <button type="button" disabled={busy} onClick={() => save(false)} className="h-12 px-5 rounded-2xl border-2 border-[#063D2E] text-[#063D2E] font-bold flex items-center gap-2 disabled:opacity-50 active:scale-95">
                <Save className="w-5 h-5" /> {tr("shop.save")}
              </button>
              <button type="button" disabled={busy} onClick={() => save(true)} className="h-12 px-5 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 disabled:opacity-50 active:scale-95">
                <Printer className="w-5 h-5" /> {tr("shop.save_print", { n: pieces })}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
