// ============================================================================
// Live shop preview for the product editor.
//
// Mirrors apps/storefront/index.html: the product CARD (grid) and the product
// PAGE (photos, price, stock, description, characteristics, colour / size
// selectors), in French, Arabic (right-to-left) or English — exactly what a
// customer will see. Clicking a colour/size shows that variant's own photo,
// price and stock. A checklist tells the owner what is still missing.
//
// Keep the visual rules in sync with the storefront:
//   badge = Nouveau (new arrival) → Populaire (featured) → Promo (discount)
//   colour dots = the real colours of the variants (never invented)
//   no ratings / reviews are shown (the shop has none)
// ============================================================================

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Circle, Heart, LayoutGrid, Link2, ShoppingCart, SquareStack } from "lucide-react";
import { useT } from "../i18n";
import { mediaUrl, PLACEHOLDER_IMG } from "../api/adminClient";
import { notifyClientSuccess } from "../utils/clientNotifier";
import type { EditorVariant, VariantAxis } from "./VariantManager";

type Lang = "fr" | "ar" | "en";

export type PreviewCheck = { ok: boolean; label: string; optional?: boolean };

type Props = {
  names: Record<Lang, string>;
  descriptions: Record<Lang, string>;
  brandName?: string;
  mainImageUrl: string;
  galleryUrls: string[];
  sellingPriceDzd: number;
  previousPriceDzd: number | "";
  discountPercent: number;
  isFeatured: boolean;
  isNewArrival: boolean;
  status: string;
  variants: EditorVariant[];
  axes: VariantAxis[];
  dataAttributes: any[];
  attributeValues: Record<string, string>;
  checks: PreviewCheck[];
  shopLink?: string;
};

// The shop's own wording (apps/storefront/index.html → I18N).
const SHOP: Record<Lang, Record<string, string>> = {
  fr: { addToCart: "Ajouter au panier", buyNow: "Acheter maintenant", inStock: "En stock", outOfStock: "Rupture de stock", qty: "Quantité" },
  ar: { addToCart: "أضف إلى السلة", buyNow: "اشتر الآن", inStock: "متوفر", outOfStock: "نفد المخزون", qty: "الكمية" },
  en: { addToCart: "Add to Bag", buyNow: "Buy Now", inStock: "In Stock", outOfStock: "Out of Stock", qty: "Quantity" },
};

function formatDZD(n: number): string {
  return String(Math.round(Number(n) || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " DA";
}

function labelFor(attr: any, lang: Lang): string {
  if (lang === "ar") return attr.label_ar || attr.label_fr || attr.attr_key;
  if (lang === "en") return attr.label_en || attr.label_fr || attr.attr_key;
  return attr.label_fr || attr.attr_key;
}

function Img({ src, className, alt }: { src?: string; className?: string; alt?: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  const url = !src || failed ? PLACEHOLDER_IMG : mediaUrl(src);
  return <img src={url} alt={alt || ""} className={className} onError={() => setFailed(true)} />;
}

export function StorefrontPreview(props: Props) {
  const t = useT();
  const [mode, setMode] = useState<"card" | "page">("card");
  const [lang, setLang] = useState<Lang>("fr");
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [activePhoto, setActivePhoto] = useState<string | null>(null);

  const variants = props.variants.filter((v) => v.is_active !== false);
  const name = props.names[lang] || props.names.fr;
  const description = props.descriptions[lang] || props.descriptions.fr;
  const missingTranslation = lang !== "fr" && (!props.names[lang] || (!props.descriptions[lang] && props.descriptions.fr));

  // Colour codes from the category's variant axes.
  const hexByValue = useMemo(() => {
    const map: Record<string, string> = {};
    props.axes.forEach((a) => (a.options || []).forEach((o) => {
      if (o.color_hex) map[o.value] = o.color_hex;
    }));
    return map;
  }, [props.axes]);

  const swatches = useMemo(() => {
    const out: string[] = [];
    variants.forEach((v) => Object.values(v.attributes || {}).forEach((val) => {
      const hex = hexByValue[val];
      if (hex && !out.includes(hex)) out.push(hex);
    }));
    return out.slice(0, 6);
  }, [variants, hexByValue]);

  // Default selection: first variant in stock (like the shop).
  useEffect(() => {
    const first = variants.find((v) => Number(v.stock_qty) > 0) || variants[0];
    setSelected(first ? { ...(first.attributes || {}) } : {});
    setActivePhoto(null);
  }, [props.variants.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const currentVariant =
    variants.find((v) => Object.entries(selected).every(([k, val]) => (v.attributes || {})[k] === val)) || variants[0];
  const totalStock = variants.reduce((s, v) => s + (Number(v.stock_qty) || 0), 0);
  const variantStock = currentVariant ? Number(currentVariant.stock_qty) || 0 : 0;
  const unitPrice =
    currentVariant && currentVariant.price_override_dzd !== null && currentVariant.price_override_dzd !== undefined && String(currentVariant.price_override_dzd) !== ""
      ? Number(currentVariant.price_override_dzd)
      : Number(props.sellingPriceDzd) || 0;
  const prev = Number(props.previousPriceDzd) || 0;
  const badge = props.isNewArrival ? "Nouveau" : props.isFeatured ? "Populaire" : props.discountPercent > 0 ? "Promo" : null;
  const gallery = [props.mainImageUrl, ...props.galleryUrls].filter((u, i, arr) => u && arr.indexOf(u) === i);
  const pagePhoto = activePhoto || (currentVariant as any)?.image_url || props.mainImageUrl;
  const sh = SHOP[lang];
  const characteristics = props.dataAttributes
    .map((a) => ({ label: labelFor(a, lang), value: props.attributeValues[a.attr_key] }))
    .filter((c) => String(c.value || "").trim());

  return (
    <div className="bg-[#FAF9F6] p-3.5 rounded-3xl border border-[#D4AF62]/40 space-y-3 w-full">
      {/* Controls */}
      <div className="flex items-center justify-between gap-2">
        <div className="inline-flex rounded-xl bg-white border border-gray-200 p-0.5 text-[11px] font-bold">
          <button type="button" onClick={() => setMode("card")}
            className={`px-2.5 py-1 rounded-lg flex items-center gap-1 ${mode === "card" ? "bg-[#063D2E] text-[#D4AF62]" : "text-gray-600"}`}>
            <LayoutGrid className="w-3.5 h-3.5" /> {t("preview.mode_card")}
          </button>
          <button type="button" onClick={() => setMode("page")}
            className={`px-2.5 py-1 rounded-lg flex items-center gap-1 ${mode === "page" ? "bg-[#063D2E] text-[#D4AF62]" : "text-gray-600"}`}>
            <SquareStack className="w-3.5 h-3.5" /> {t("preview.mode_page")}
          </button>
        </div>
        <div className="inline-flex rounded-xl bg-white border border-gray-200 p-0.5 text-[11px] font-bold">
          {(["fr", "ar", "en"] as Lang[]).map((l) => (
            <button key={l} type="button" onClick={() => setLang(l)}
              className={`px-2 py-1 rounded-lg ${lang === l ? "bg-[#D4AF62] text-[#02291F]" : "text-gray-600"}`}>
              {l === "ar" ? "ع" : l.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {props.status !== "published" && (
        <p className="text-[11px] font-bold text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-3 py-1.5">
          {t("preview.not_published")}
        </p>
      )}
      {missingTranslation && (
        <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-3 py-1.5 flex gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" /> {t("preview.missing_translation")}
        </p>
      )}

      <div dir={lang === "ar" ? "rtl" : "ltr"}>
        {mode === "card" ? (
          /* ---------------- Product card (same structure as the shop grid) ---------------- */
          <article className="bg-white rounded-2xl overflow-hidden border border-[#D4AF62]/25 shadow-[0_10px_30px_-12px_rgba(2,41,31,0.25)] max-w-[300px] mx-auto">
            <div className="relative aspect-square bg-[#F3EFE6] overflow-hidden">
              <Img src={props.mainImageUrl} alt={name} className="w-full h-full object-cover" />
              {badge && (
                <span className={`absolute top-2.5 start-2.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider shadow-sm ${
                  badge === "Promo" ? "bg-red-600 text-white" : "bg-[#063D2E] text-[#E8D4A5] border border-[#D4AF62]/40"}`}>
                  {badge}
                </span>
              )}
              <span className="absolute top-2.5 end-2.5 w-8 h-8 rounded-full bg-white/95 flex items-center justify-center shadow-md">
                <Heart className="w-4 h-4 text-[#202923]/70" />
              </span>
            </div>
            <div className="p-4 space-y-2.5">
              <p className="text-[10px] font-bold uppercase tracking-widest text-[#9A7A35] truncate">{props.brandName || "MUS LUXURY"}</p>
              <h3 className="font-bold text-[#202923] text-base line-clamp-1">{name || t("preview.default_name")}</h3>
              <div className="flex flex-wrap items-center justify-between gap-1">
                <div className="flex items-baseline gap-1.5">
                  <span className="text-lg font-extrabold text-[#063D2E]">{formatDZD(props.sellingPriceDzd)}</span>
                  {prev > 0 && <span className="text-xs text-gray-400 line-through">{formatDZD(prev)}</span>}
                </div>
                {props.discountPercent > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-red-600 text-white text-[10px] font-bold">-{props.discountPercent}%</span>
                )}
              </div>
              {swatches.length > 0 && (
                <div className="flex items-center gap-1.5">
                  {swatches.map((hex) => (
                    <span key={hex} className="w-4 h-4 rounded-full border border-gray-300" style={{ backgroundColor: hex }} />
                  ))}
                </div>
              )}
              <button type="button" disabled={variants.length > 0 && totalStock <= 0}
                className={`w-full py-2.5 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 ${
                  variants.length > 0 && totalStock <= 0 ? "bg-gray-200 text-gray-500" : "bg-[#063D2E] text-white"}`}>
                <ShoppingCart className="w-4 h-4" />
                {variants.length > 0 && totalStock <= 0 ? sh.outOfStock : sh.addToCart}
              </button>
            </div>
          </article>
        ) : (
          /* ---------------- Product page (same blocks as the shop's product pop-up) ---------------- */
          <div className="bg-white rounded-2xl border border-[#D4AF62]/25 overflow-hidden">
            <div className="relative aspect-square bg-[#F3EFE6]">
              <Img src={pagePhoto} alt={name} className="w-full h-full object-cover" />
            </div>
            {gallery.length > 1 && (
              <div className="flex gap-1.5 p-2 overflow-x-auto">
                {gallery.map((u) => (
                  <button key={u} type="button" onClick={() => setActivePhoto(u)}
                    className={`w-12 h-12 rounded-lg overflow-hidden border-2 shrink-0 ${pagePhoto === u ? "border-[#D4AF62]" : "border-transparent"}`}>
                    <Img src={u} className="w-full h-full object-cover" />
                  </button>
                ))}
              </div>
            )}
            <div className="p-4 space-y-3 text-start">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#9A7A35]">{props.brandName || "MUS LUXURY"}</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                  variantStock > 0 ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
                  {variantStock > 0 ? `● ${sh.inStock} (${variantStock})` : `✕ ${sh.outOfStock}`}
                </span>
              </div>
              <h3 className="font-serif text-xl font-bold text-[#063D2E] leading-snug">{name || t("preview.default_name")}</h3>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-extrabold text-[#9A7A35]">{formatDZD(unitPrice)}</span>
                {prev > unitPrice && <span className="text-sm text-gray-400 line-through">{formatDZD(prev)}</span>}
                {props.discountPercent > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-red-600 text-white text-[10px] font-bold">-{props.discountPercent}%</span>
                )}
              </div>
              {description ? (
                <p className="text-xs text-[#202923]/80 leading-relaxed whitespace-pre-line">{description}</p>
              ) : (
                <p className="text-xs italic text-gray-400">{t("preview.no_description")}</p>
              )}
              {characteristics.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {characteristics.map((c) => (
                    <span key={c.label} className="px-2 py-1 rounded-lg bg-[#F8F6F0] border border-[#D4AF62]/30 text-[11px]">
                      <strong className="text-[#063D2E]">{c.label} :</strong> {c.value}
                    </span>
                  ))}
                </div>
              )}
              {props.axes.map((axis) => {
                const values = Array.from(new Set(variants.map((v) => (v.attributes || {})[axis.attr_key]).filter(Boolean)));
                if (!values.length) return null;
                return (
                  <div key={axis.attr_key} className="space-y-1.5">
                    <p className="text-[11px] text-[#202923]/80">
                      {labelFor(axis, lang)} : <strong className="text-[#063D2E]">{selected[axis.attr_key] || "—"}</strong>
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {values.map((val) => {
                        const active = selected[axis.attr_key] === val;
                        const hex = hexByValue[val];
                        return (
                          <button key={val} type="button"
                            onClick={() => { setSelected((s) => ({ ...s, [axis.attr_key]: val })); setActivePhoto(null); }}
                            className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border flex items-center gap-1.5 ${
                              active ? "bg-[#063D2E] text-[#E8D4A5] border-[#063D2E]" : "bg-white text-[#202923] border-gray-300"}`}>
                            {hex && <span className="w-3 h-3 rounded-full border border-white/60" style={{ backgroundColor: hex }} />}
                            {val}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
              <div className="grid grid-cols-2 gap-2 pt-1">
                <span className="py-2.5 rounded-xl bg-gradient-to-r from-[#D4AF62] to-[#E8D4A5] text-[#02291F] text-[11px] font-extrabold uppercase text-center flex items-center justify-center gap-1.5">
                  <ShoppingCart className="w-3.5 h-3.5" /> {sh.addToCart}
                </span>
                <span className="py-2.5 rounded-xl bg-[#063D2E] text-[#E8D4A5] text-[11px] font-bold uppercase text-center">{sh.buyNow}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Ready-for-the-shop checklist */}
      <div className="bg-white rounded-2xl border border-gray-200 p-3 space-y-1.5">
        <p className="text-[11px] font-extrabold text-[#063D2E]">{t("preview.checklist_title")}</p>
        {props.checks.map((c) => (
          <p key={c.label} className={`text-[11px] flex items-center gap-1.5 ${c.ok ? "text-emerald-700" : c.optional ? "text-gray-500" : "text-amber-800"}`}>
            {c.ok ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Circle className="w-3.5 h-3.5" />}
            {c.label}
            {!c.ok && c.optional && <span className="text-[10px] text-gray-400">({t("preview.optional")})</span>}
          </p>
        ))}
        {props.shopLink && (
          <button type="button"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(props.shopLink!);
                notifyClientSuccess(t("preview.link_copied"), props.shopLink!);
              } catch {
                notifyClientSuccess(t("preview.copy_link"), props.shopLink!);
              }
            }}
            className="mt-1 w-full inline-flex items-center justify-center gap-1.5 py-1.5 rounded-lg border border-[#D4AF62] text-[#063D2E] text-[11px] font-bold hover:bg-[#D4AF62]/10"
            title={props.shopLink}>
            <Link2 className="w-3.5 h-3.5" /> {t("preview.copy_link")}
          </button>
        )}
      </div>
    </div>
  );
}
