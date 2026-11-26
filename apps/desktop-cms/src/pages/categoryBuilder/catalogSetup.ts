// Attribute types, category icons, colour palette and the draft shapes of the category builder.
import { Crown, Footprints, Gem, Glasses, Shirt, ShoppingBag, Sparkles, Store, Tag, Watch } from "lucide-react";
import { tr } from "../../i18n/translations";

export const ATTRIBUTE_TYPES = [
  "short_text",
  "long_text",
  "number",
  "price",
  "boolean",
  "single_select",
  "multi_select",
  "color",
  "size",
  "image",
  "date",
  "measurement",
  "brand",
  "barcode_sku",
];

// Names staff read for the technical attribute types.
export const typeLabel = (t: string) => (ATTRIBUTE_TYPES.includes(t) ? tr(`cb.type_${t}`) : t);

export const LUXURY_ICONS = [
  { key: "bag", icon: ShoppingBag },
  { key: "shoes", icon: Footprints },
  { key: "shirt", icon: Shirt },
  { key: "sparkles", icon: Sparkles },
  { key: "gem", icon: Gem },
  { key: "crown", icon: Crown },
  { key: "glasses", icon: Glasses },
  { key: "watch", icon: Watch },
  { key: "tag", icon: Tag },
  { key: "store", icon: Store },
];

export function getCategoryIconComponent(slugOrName: string, iconKey?: string) {
  if (iconKey) {
    const found = LUXURY_ICONS.find((i) => i.key === iconKey);
    if (found) return found.icon;
  }
  const s = (slugOrName || "").toLowerCase();
  if (s.includes("t-shirt") || s.includes("pret-a-porter") || s.includes("vetement") || s.includes("polo")) return Shirt;
  if (s.includes("sac") || s.includes("bag") || s.includes("maroquinerie")) return ShoppingBag;
  if (s.includes("chauss") || s.includes("shoe") || s.includes("basket") || s.includes("soulier")) return Footprints;
  if (s.includes("chal") || s.includes("châl") || s.includes("soie") || s.includes("foulard")) return Sparkles;
  if (s.includes("maquillage") || s.includes("cosm") || s.includes("beaute")) return Gem;
  if (s.includes("chapeau") || s.includes("casquette") || s.includes("beret")) return Crown;
  if (s.includes("lunette") || s.includes("soleil") || s.includes("optique")) return Glasses;
  if (s.includes("montre") || s.includes("watch") || s.includes("horlog")) return Watch;
  return Tag;
}

export interface DraftAttributeOption {
  value: string;
  label_fr?: string;
  label_ar?: string;
  label_en?: string;
  color_hex?: string;
  display_order?: number;
}

export interface DraftAttribute {
  attr_key: string;
  label_fr: string;
  label_ar: string;
  label_en: string;
  input_type: string;
  unit: string;
  is_required: boolean;
  is_visible_on_storefront: boolean;
  is_filterable: boolean;
  is_variant_axis: boolean;
  options_csv: string;
  rich_options?: DraftAttributeOption[];
}

export interface CategoryPreset {
  id: string;
  name: string;
  name_en: string;
  name_ar: string;
  slug: string;
  iconName: string;
  description_fr: string;
  description_en: string;
  description_ar: string;
  image_url: string;
  banner_url: string;
  attributes: DraftAttribute[];
}

/** Name of an icon / a palette shade in the language in use. */
export const iconLabel = (key: string, short = false) => tr(`cb.icon_${key}${short ? "_short" : ""}`);
export const paletteLabel = (hex: string) => tr(`cb.pal_${hex.replace("#", "")}`);

export const LUXURY_PALETTE = [
  { name: "Noir Profond", hex: "#0A0A0A" },
  { name: "Blanc Pur", hex: "#FFFFFF" },
  { name: "Vert Émeraude Mus", hex: "#063D2E" },
  { name: "Or Impérial", hex: "#D4AF62" },
  { name: "Bordeaux Royal", hex: "#4A0E17" },
  { name: "Bleu Nuit", hex: "#0F1D38" },
  { name: "Camel Cuir", hex: "#C19A6B" },
  { name: "Gris Anthracite", hex: "#36454F" },
  { name: "Rose Nude", hex: "#D7A287" },
  { name: "Rouge Rubis", hex: "#9B111E" },
];
