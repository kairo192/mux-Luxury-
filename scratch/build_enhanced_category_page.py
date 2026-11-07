import os

new_code = '''import { readDraft, writeDraft, clearDraft } from "../utils/draftStorage";
import React, { useEffect, useState } from "react";
import { DesktopCmsApi } from "../api/adminClient";
import { notifyClientError, notifyClientSuccess, notifyClientWarning } from "../utils/clientNotifier";
import {
  Tags,
  Plus,
  Search,
  Edit3,
  Trash2,
  Archive,
  Eye,
  EyeOff,
  Sparkles,
  Watch,
  Glasses,
  Crown,
  Gem,
  ShoppingBag,
  Footprints,
  Tag,
  Store,
  Check,
  X,
  Layers,
  SlidersHorizontal,
  RefreshCw,
  AlertTriangle,
  ArrowUpDown,
  Filter,
  ArrowUp,
  ArrowDown,
  Palette,
  Shirt,
  Image as ImageIcon,
} from "lucide-react";

const ATTRIBUTE_TYPES = [
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

const LUXURY_ICONS = [
  { key: "shirt", label: "Prêt-à-porter & Mode", icon: Shirt },
  { key: "bag", label: "Sacs & Maroquinerie", icon: ShoppingBag },
  { key: "shoes", label: "Chaussures & Souliers", icon: Footprints },
  { key: "sparkles", label: "Châles & Soieries", icon: Sparkles },
  { key: "gem", label: "Maquillage & Beauté", icon: Gem },
  { key: "crown", label: "Chapeaux & Couvre-chefs", icon: Crown },
  { key: "glasses", label: "Lunettes & Optique", icon: Glasses },
  { key: "watch", label: "Montres & Horlogerie", icon: Watch },
  { key: "tag", label: "Accessoires & Mode", icon: Tag },
  { key: "store", label: "Boutique & Vitrine", icon: Store },
];

function getCategoryIconComponent(slugOrName: string, iconKey?: string) {
  if (iconKey) {
    const found = LUXURY_ICONS.find((i) => i.key === iconKey);
    if (found) return found.icon;
  }
  const s = (slugOrName || "").toLowerCase();
  if (s.includes("t-shirt") || s.includes("pret") || s.includes("vetement") || s.includes("shirt")) return Shirt;
  if (s.includes("sac") || s.includes("bag") || s.includes("maroquinerie")) return ShoppingBag;
  if (s.includes("chauss") || s.includes("shoe") || s.includes("basket")) return Footprints;
  if (s.includes("chal") || s.includes("châl") || s.includes("soie") || s.includes("foulard")) return Sparkles;
  if (s.includes("maquillage") || s.includes("cosm") || s.includes("beaute")) return Gem;
  if (s.includes("chapeau") || s.includes("casquette") || s.includes("beret")) return Crown;
  if (s.includes("lunette") || s.includes("soleil") || s.includes("optique")) return Glasses;
  if (s.includes("montre") || s.includes("watch") || s.includes("horlog")) return Watch;
  return Tag;
}

export interface OptionDetail {
  value: string;
  label_fr?: string;
  label_ar?: string;
  label_en?: string;
  color_hex?: string | null;
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
  is_filterable: boolean;
  is_variant_axis: boolean;
  options_csv: string;
  rich_options?: OptionDetail[];
}

export interface CategoryPreset {
  id: string;
  name: string;
  icon: any;
  slug: string;
  name_fr: string;
  name_ar: string;
  name_en: string;
  description_fr: string;
  image_url: string;
  banner_url: string;
  attributes: DraftAttribute[];
}

const LUXURY_PALETTE = [
  { name: "Noir", hex: "#1A1A1A" },
  { name: "Blanc", hex: "#FFFFFF" },
  { name: "Bordeaux", hex: "#5B1E31" },
  { name: "Vert Émeraude", hex: "#063D2E" },
  { name: "Or Impérial", hex: "#D4AF62" },
  { name: "Bleu Marine", hex: "#00205B" },
  { name: "Rouge Rubis", hex: "#C8102E" },
  { name: "Camel Royal", hex: "#C19A6B" },
  { name: "Rose Poudré", hex: "#ED64A6" },
  { name: "Gris Perle", hex: "#9E9E9E" },
];

const STANDARD_ASSET_IMAGES = [
  { label: "Sacs de Luxe", url: "/assets/cat_sacs.jpg" },
  { label: "Chaussures & Baskets", url: "/assets/cat_chaussures.jpg" },
  { label: "Châles & Soie", url: "/assets/cat_chale.jpg" },
  { label: "Coffret Maquillage", url: "/assets/cat_maquillage.jpg" },
  { label: "Chapeaux Classiques", url: "/assets/cat_chapeau.jpg" },
  { label: "Casquettes Urbaines", url: "/assets/prod_casquette_ny.jpg" },
  { label: "Lunettes Solaires", url: "/assets/prod_lunettes_soleil.jpg" },
  { label: "Montre Chronographe", url: "/assets/prod_montre_or.jpg" },
  { label: "Accessoires & Bijoux", url: "/assets/prod_accessoires_or.jpg" },
  { label: "Bannière Podium Or", url: "/assets/hero_bag_clean.jpg" },
];

const CATEGORY_PRESETS: CategoryPreset[] = [
  {
    id: "t-shirts",
    name: "T-shirts & Prêt-à-porter",
    icon: Shirt,
    slug: "t-shirts",
    name_fr: "T-shirts & Prêt-à-porter",
    name_ar: "قمصان وتيشرتات راقية",
    name_en: "T-Shirts & Designer Apparel",
    description_fr: "T-shirts d'exception, polos raffinés et créations prêt-à-porter confectionnés en coton Pima noble.",
    image_url: "/assets/cat_chaussures.jpg",
    banner_url: "/assets/hero_bag_clean.jpg",
    attributes: [
      {
        attr_key: "color",
        label_fr: "Couleur",
        label_ar: "اللون",
        label_en: "Color",
        input_type: "color",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "Noir, Blanc, Bordeaux, Vert Émeraude, Bleu Marine, Rouge",
        rich_options: [
          { value: "Noir", label_fr: "Noir", color_hex: "#1A1A1A" },
          { value: "Blanc", label_fr: "Blanc", color_hex: "#FFFFFF" },
          { value: "Bordeaux", label_fr: "Bordeaux", color_hex: "#5B1E31" },
          { value: "Vert Émeraude", label_fr: "Vert Émeraude", color_hex: "#063D2E" },
          { value: "Bleu Marine", label_fr: "Bleu Marine", color_hex: "#00205B" },
          { value: "Rouge", label_fr: "Rouge", color_hex: "#C8102E" },
        ],
      },
      {
        attr_key: "size",
        label_fr: "Taille",
        label_ar: "المقاس",
        label_en: "Size",
        input_type: "size",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "XS, S, M, L, XL, XXL, 3XL",
        rich_options: [
          { value: "XS", label_fr: "XS" },
          { value: "S", label_fr: "S" },
          { value: "M", label_fr: "M" },
          { value: "L", label_fr: "L" },
          { value: "XL", label_fr: "XL" },
          { value: "XXL", label_fr: "XXL" },
          { value: "3XL", label_fr: "3XL" },
        ],
      },
      {
        attr_key: "material",
        label_fr: "Matière",
        label_ar: "الخامة",
        label_en: "Material",
        input_type: "single_select",
        unit: "",
        is_required: false,
        is_filterable: true,
        is_variant_axis: false,
        options_csv: "100% Coton Pima, Coton Peigné Bio, Lin & Soie, Jersey Doux",
        rich_options: [
          { value: "100% Coton Pima", label_fr: "100% Coton Pima" },
          { value: "Coton Peigné Bio", label_fr: "Coton Peigné Bio" },
          { value: "Lin & Soie", label_fr: "Lin & Soie" },
          { value: "Jersey Doux", label_fr: "Jersey Doux" },
        ],
      },
      {
        attr_key: "fit",
        label_fr: "Coupe",
        label_ar: "القصّة",
        label_en: "Fit",
        input_type: "single_select",
        unit: "",
        is_required: false,
        is_filterable: true,
        is_variant_axis: false,
        options_csv: "Coupe Droite (Regular), Coupe Ajustée (Slim), Coupe Oversize",
        rich_options: [
          { value: "Coupe Droite (Regular)", label_fr: "Coupe Droite (Regular)" },
          { value: "Coupe Ajustée (Slim)", label_fr: "Coupe Ajustée (Slim)" },
          { value: "Coupe Oversize", label_fr: "Coupe Oversize" },
        ],
      },
    ],
  },
  {
    id: "chaussures",
    name: "Chaussures & Sneakers",
    icon: Footprints,
    slug: "chaussures",
    name_fr: "Chaussures & Souliers",
    name_ar: "أحذية وأحذية رياضية",
    name_en: "Shoes & Sneakers",
    description_fr: "Souliers, escarpins et sneakers d'exception confectionnés dans les plus beaux cuirs.",
    image_url: "/assets/cat_chaussures.jpg",
    banner_url: "/assets/hero_bag_clean.jpg",
    attributes: [
      {
        attr_key: "shoe_size",
        label_fr: "Pointure",
        label_ar: "المقاس",
        label_en: "Shoe Size",
        input_type: "size",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "36, 37, 38, 39, 40, 41, 42, 43, 44, 45",
        rich_options: ["36", "37", "38", "39", "40", "41", "42", "43", "44", "45"].map((v) => ({ value: v, label_fr: v })),
      },
      {
        attr_key: "color",
        label_fr: "Couleur",
        label_ar: "اللون",
        label_en: "Color",
        input_type: "color",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "Blanc & Noir, Noir, Or, Blanc Pur",
        rich_options: [
          { value: "Blanc & Noir", label_fr: "Blanc & Noir", color_hex: "#F5F5F5" },
          { value: "Noir", label_fr: "Noir", color_hex: "#1B1B1B" },
          { value: "Or", label_fr: "Or", color_hex: "#D4AF62" },
          { value: "Blanc Pur", label_fr: "Blanc Pur", color_hex: "#FFFFFF" },
        ],
      },
      {
        attr_key: "leather_type",
        label_fr: "Matière",
        label_ar: "الخامة",
        label_en: "Material",
        input_type: "single_select",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: false,
        options_csv: "Cuir nappa souple, Cuir verni, Daim de veau, Toile technique",
      },
      {
        attr_key: "gender",
        label_fr: "Genre",
        label_ar: "الجنس",
        label_en: "Gender",
        input_type: "single_select",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: false,
        options_csv: "Femme, Homme, Unisexe",
      },
    ],
  },
  {
    id: "sacs",
    name: "Maroquinerie & Sacs",
    icon: ShoppingBag,
    slug: "sacs",
    name_fr: "Sacs & Maroquinerie",
    name_ar: "حقائب ومصنوعات جلدية",
    name_en: "Bags & Leather Goods",
    description_fr: "Sacs à main emblématiques, pochettes et maroquinerie d'apparat au design intemporel.",
    image_url: "/assets/cat_sacs.jpg",
    banner_url: "/assets/hero_bag_clean.jpg",
    attributes: [
      {
        attr_key: "color",
        label_fr: "Couleur",
        label_ar: "اللون",
        label_en: "Color",
        input_type: "color",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "Bordeaux, Vert Émeraude, Noir Onyx, Beige Sable, Rose Poudré",
        rich_options: [
          { value: "Bordeaux", label_fr: "Bordeaux", color_hex: "#5B2333" },
          { value: "Vert Émeraude", label_fr: "Vert Émeraude", color_hex: "#063D2E" },
          { value: "Noir Onyx", label_fr: "Noir Onyx", color_hex: "#1B1B1B" },
          { value: "Beige Sable", label_fr: "Beige Sable", color_hex: "#D9C3A9" },
          { value: "Rose Poudré", label_fr: "Rose Poudré", color_hex: "#C77D8A" },
        ],
      },
      {
        attr_key: "size",
        label_fr: "Format / Taille",
        label_ar: "الحجم",
        label_en: "Format",
        input_type: "size",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "Mini, Petit (S), Standard (M), Grand (L), Cabas",
        rich_options: [
          { value: "Mini", label_fr: "Mini" },
          { value: "Petit (S)", label_fr: "Petit (S)" },
          { value: "Standard (M)", label_fr: "Standard (M)" },
          { value: "Grand (L)", label_fr: "Grand (L)" },
          { value: "Cabas", label_fr: "Cabas" },
        ],
      },
      {
        attr_key: "bag_type",
        label_fr: "Type de sac",
        label_ar: "نوع الحقيبة",
        label_en: "Bag Type",
        input_type: "single_select",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: false,
        options_csv: "Sac à main, Sac bandoulière, Pochette de soirée, Sac de voyage",
      },
      {
        attr_key: "dimensions",
        label_fr: "Dimensions",
        label_ar: "الأبعاد",
        label_en: "Dimensions",
        input_type: "measurement",
        unit: "cm",
        is_required: false,
        is_filterable: false,
        is_variant_axis: false,
        options_csv: "",
      },
    ],
  },
  {
    id: "montres",
    name: "Montres & Horlogerie",
    icon: Watch,
    slug: "les-montres",
    name_fr: "Montres & Horlogerie",
    name_ar: "ساعات فاخرة",
    name_en: "Watches & Timepieces",
    description_fr: "Garde-temps d'exception, chronographes de précision et finitions or et acier noble.",
    image_url: "/assets/prod_montre_or.jpg",
    banner_url: "/assets/hero_bag_clean.jpg",
    attributes: [
      {
        attr_key: "dial_color",
        label_fr: "Couleur du cadran",
        label_ar: "لون الميناء",
        label_en: "Dial Color",
        input_type: "color",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "Noir & Or, Vert Émeraude & Or, Blanc Nacré, Bleu Nuit",
        rich_options: [
          { value: "Noir & Or", label_fr: "Noir & Or", color_hex: "#1A2421" },
          { value: "Vert Émeraude & Or", label_fr: "Vert Émeraude & Or", color_hex: "#063D2E" },
          { value: "Blanc Nacré", label_fr: "Blanc Nacré", color_hex: "#FAF5EE" },
          { value: "Bleu Nuit", label_fr: "Bleu Nuit", color_hex: "#0B1B3D" },
        ],
      },
      {
        attr_key: "strap_material",
        label_fr: "Matière du bracelet",
        label_ar: "خامة السوار",
        label_en: "Strap Material",
        input_type: "single_select",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "Acier doré, Cuir véritable noir, Cuir crocodile marron, Maille milanaise",
        rich_options: [
          { value: "Acier doré", label_fr: "Acier doré" },
          { value: "Cuir véritable noir", label_fr: "Cuir véritable noir" },
          { value: "Cuir crocodile marron", label_fr: "Cuir crocodile marron" },
          { value: "Maille milanaise", label_fr: "Maille milanaise" },
        ],
      },
      {
        attr_key: "movement",
        label_fr: "Mouvement",
        label_ar: "حركة الساعة",
        label_en: "Movement",
        input_type: "single_select",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: false,
        options_csv: "Chronographe Quartz Précision, Automatique Suisse, Mécanique",
      },
      {
        attr_key: "water_resistance",
        label_fr: "Étanchéité",
        label_ar: "مقاومة الماء",
        label_en: "Water Resistance",
        input_type: "short_text",
        unit: "",
        is_required: true,
        is_filterable: false,
        is_variant_axis: false,
        options_csv: "",
      },
    ],
  },
  {
    id: "beaute",
    name: "Cosmétiques & Parfumerie",
    icon: Gem,
    slug: "maquillage",
    name_fr: "Cosmétiques & Parfumerie",
    name_ar: "مستحضرات تجميل وعطور",
    name_en: "Cosmetics & Fragrances",
    description_fr: "Senteurs rares d'Orient, coffrets de maquillage et soins sublimateurs de teint.",
    image_url: "/assets/cat_maquillage.jpg",
    banner_url: "/assets/hero_bag_clean.jpg",
    attributes: [
      {
        attr_key: "shade",
        label_fr: "Teinte / Nuance",
        label_ar: "الدرجة",
        label_en: "Shade",
        input_type: "color",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "Coffret Rose & Nude 01, Coffret Rubis & Or 02, Nude Éclat, Rouge Passion",
        rich_options: [
          { value: "Coffret Rose & Nude 01", label_fr: "Coffret Rose & Nude 01", color_hex: "#B6465F" },
          { value: "Coffret Rubis & Or 02", label_fr: "Coffret Rubis & Or 02", color_hex: "#8E1B2B" },
          { value: "Nude Éclat", label_fr: "Nude Éclat", color_hex: "#D99B82" },
          { value: "Rouge Passion", label_fr: "Rouge Passion", color_hex: "#B91C1C" },
        ],
      },
      {
        attr_key: "volume",
        label_fr: "Contenance / Format",
        label_ar: "الحجم",
        label_en: "Volume",
        input_type: "measurement",
        unit: "ml / g",
        is_required: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "30 ml, 50 ml, 100 ml, Coffret Complet",
        rich_options: [
          { value: "30 ml", label_fr: "30 ml" },
          { value: "50 ml", label_fr: "50 ml" },
          { value: "100 ml", label_fr: "100 ml" },
          { value: "Coffret Complet", label_fr: "Coffret Complet" },
        ],
      },
      {
        attr_key: "finish",
        label_fr: "Fini",
        label_ar: "اللمسة النهائية",
        label_en: "Finish",
        input_type: "single_select",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: false,
        options_csv: "Satiné & Velours, Mat longue tenue, Brillant Haute Lumière",
      },
    ],
  },
  {
    id: "lunettes",
    name: "Lunettes & Solaires",
    icon: Glasses,
    slug: "les-lunettes",
    name_fr: "Lunettes & Solaires",
    name_ar: "نظارات شمسية وراقية",
    name_en: "Eyewear & Sunglasses",
    description_fr: "Montures affirmées, verres UV400 haute protection et finitions or et écaille.",
    image_url: "/assets/prod_lunettes_soleil.jpg",
    banner_url: "/assets/hero_bag_clean.jpg",
    attributes: [
      {
        attr_key: "frame_color",
        label_fr: "Couleur monture",
        label_ar: "لون الإطار",
        label_en: "Frame Color",
        input_type: "color",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "Écaille & Or, Noir Intense, Doré Prestige",
        rich_options: [
          { value: "Écaille & Or", label_fr: "Écaille & Or", color_hex: "#4A2E1B" },
          { value: "Noir Intense", label_fr: "Noir Intense", color_hex: "#141414" },
          { value: "Doré Prestige", label_fr: "Doré Prestige", color_hex: "#D4AF62" },
        ],
      },
      {
        attr_key: "lens_type",
        label_fr: "Type de verres",
        label_ar: "نوع العدسات",
        label_en: "Lens Type",
        input_type: "single_select",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: false,
        options_csv: "Polarisés Dégradés, Miroir Or, Teintés Gris Neutre",
      },
      {
        attr_key: "uv_protection",
        label_fr: "Protection UV",
        label_ar: "حماية الأشعة",
        label_en: "UV Protection",
        input_type: "short_text",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: false,
        options_csv: "UV400 Catégorie 3",
      },
    ],
  },
];
'''

print("Header ready.")

