import React from "react";
import { Eye, Heart, ShoppingBag, Sparkles, Star } from "lucide-react";
import { EditorVariant } from "./VariantManager";

type Props = {
  name: string;
  brandName?: string;
  categoryName?: string;
  mainImageUrl: string;
  sellingPriceDzd: number;
  previousPriceDzd?: number | "";
  discountPercent?: number;
  isFeatured?: boolean;
  isNewArrival?: boolean;
  variants: EditorVariant[];
  colorHexMap?: Record<string, string>;
};

function formatDZD(val: number): string {
  return new Intl.NumberFormat("fr-DZ", {
    style: "currency",
    currency: "DZD",
    maximumFractionDigits: 0,
  }).format(val || 0);
}

export function LiveProductCardPreview({
  name,
  brandName,
  categoryName,
  mainImageUrl,
  sellingPriceDzd,
  previousPriceDzd,
  discountPercent = 0,
  isFeatured = false,
  isNewArrival = false,
  variants = [],
}: Props) {
  const totalStock = variants.reduce((sum, v) => sum + (Number(v.stock_qty) || 0), 0);
  const inStock = variants.length === 0 ? true : totalStock > 0;
  const sellPrice = Number(sellingPriceDzd) || 0;
  const prevPrice = Number(previousPriceDzd) || 0;
  const displayImage = mainImageUrl?.trim() || "/assets/prod_sac_chanel_hd.jpg";

  // Extract unique colors for swatches preview
  const swatches: { name: string; hex?: string }[] = [];
  const seenColors = new Set<string>();
  variants.forEach((v) => {
    const c = v.attributes?.color || v.attributes?.couleur;
    if (c && !seenColors.has(c)) {
      seenColors.add(c);
      // Look for a hex code or fallback
      swatches.push({ name: c });
    }
  });

  return (
    <div className="bg-[#FAF9F6] p-4 rounded-3xl border border-[#D4AF62]/40 shadow-xs space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[#063D2E]">
          <Eye className="w-3.5 h-3.5 text-[#D4AF62]" />
          <span className="font-serif font-bold text-xs">Aperçu Vitrine en Direct</span>
        </div>
        <span className="px-2 py-0.5 rounded-full bg-[#063D2E]/10 text-[#063D2E] text-[10px] font-bold">
          Temps réel
        </span>
      </div>

      {/* Luxury Product Card Preview */}
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-sm hover:shadow-md transition group max-w-sm mx-auto">
        {/* Image & Badges */}
        <div className="relative aspect-4/5 bg-stone-100 overflow-hidden flex items-center justify-center">
          <img
            src={displayImage}
            alt={name || "Aperçu du produit"}
            className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).src = "/assets/prod_sac_chanel_hd.jpg";
            }}
          />

          {/* Luxury Corner Badges */}
          <div className="absolute top-2.5 left-2.5 flex flex-col gap-1 z-10">
            {isNewArrival && (
              <span className="px-2 py-0.5 rounded-full bg-[#063D2E] text-[#D4AF62] text-[9px] font-extrabold uppercase tracking-wider shadow-xs">
                Nouveau
              </span>
            )}
            {isFeatured && (
              <span className="px-2 py-0.5 rounded-full bg-[#D4AF62] text-[#02291F] text-[9px] font-extrabold uppercase tracking-wider shadow-xs flex items-center gap-0.5">
                <Star className="w-2.5 h-2.5 fill-current" /> Coup de cœur
              </span>
            )}
            {discountPercent > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-rose-600 text-white text-[9px] font-extrabold shadow-xs">
                -{discountPercent}%
              </span>
            )}
          </div>

          {/* Wishlist Heart Simulation */}
          <button
            type="button"
            className="absolute top-2.5 right-2.5 w-7 h-7 rounded-full bg-white/90 backdrop-blur-xs flex items-center justify-center text-gray-400 hover:text-rose-500 shadow-xs"
          >
            <Heart className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Card Content */}
        <div className="p-3.5 space-y-2">
          {/* Brand & Category */}
          <div className="flex items-center justify-between text-[10px] text-gray-500 uppercase tracking-wider font-semibold">
            <span className="text-[#063D2E] font-bold">{brandName || "Maison Mus Luxury"}</span>
            <span>{categoryName || "Collection"}</span>
          </div>

          {/* Product Title */}
          <h4 className="font-serif font-bold text-sm text-[#202923] truncate" title={name}>
            {name || "Nom de la création de luxe"}
          </h4>

          {/* Variant Swatches Preview */}
          {swatches.length > 0 && (
            <div className="flex items-center gap-1.5 py-0.5">
              <span className="text-[10px] text-gray-500">{swatches.length} coloris :</span>
              <div className="flex items-center gap-1">
                {swatches.slice(0, 5).map((s, idx) => (
                  <span
                    key={idx}
                    className="w-3.5 h-3.5 rounded-full border border-black/20 shadow-xs inline-block"
                    style={{ backgroundColor: s.hex || "#063D2E" }}
                    title={s.name}
                  />
                ))}
                {swatches.length > 5 && (
                  <span className="text-[9px] text-gray-400 font-bold">+{swatches.length - 5}</span>
                )}
              </div>
            </div>
          )}

          {/* Price & Stock */}
          <div className="pt-1 border-t border-gray-100 flex items-baseline justify-between">
            <div className="flex items-baseline gap-1.5">
              <span className="font-extrabold text-sm text-[#063D2E]">
                {formatDZD(sellPrice)}
              </span>
              {prevPrice > sellPrice && (
                <span className="text-[11px] text-gray-400 line-through">
                  {formatDZD(prevPrice)}
                </span>
              )}
            </div>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                inStock
                  ? "bg-emerald-100 text-emerald-800"
                  : "bg-rose-100 text-rose-800"
              }`}
            >
              {inStock ? `En stock (${totalStock || "Dispo"})` : "Rupture"}
            </span>
          </div>

          {/* Storefront Action Button Simulation */}
          <button
            type="button"
            className="w-full mt-1 py-2 rounded-xl bg-gradient-to-r from-[#063D2E] to-[#0A5C45] text-[#D4AF62] font-bold text-xs flex items-center justify-center gap-1.5 shadow-xs"
          >
            <ShoppingBag className="w-3.5 h-3.5" />
            <span>Commander • Paiement à la livraison</span>
          </button>
        </div>
      </div>

      <div className="text-[10px] text-gray-500 text-center">
        Aperçu fidèle aux dimensions et au design de la vitrine client.
      </div>
    </div>
  );
}
