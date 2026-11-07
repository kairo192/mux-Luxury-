import os

filepath = 'apps/desktop-cms/src/pages/CategoryBuilderPage.tsx'
with open(filepath, 'r', encoding='utf-8') as f:
    orig = f.read()

cut_toolbar = '{/* Categories Toolbar: Search & Filters */}'
if cut_toolbar not in orig:
    print("cut_toolbar not found!")
    exit(1)

post_toolbar = orig.split(cut_toolbar)[1]

# Let's inspect everything from handleOpenEdit up to cut_toolbar
cut_modals_start = '// Open Edit Modal'
modals_and_table_part = cut_modals_start + orig.split(cut_modals_start)[1].split(cut_toolbar)[0]

script_content = '''import { readDraft, writeDraft, clearDraft } from "../utils/draftStorage";
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
  iconName: string;
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
  { name: "Noir Onyx", hex: "#1A1A1A" },
  { name: "Blanc Pur", hex: "#FFFFFF" },
  { name: "Bordeaux Royal", hex: "#5B1E31" },
  { name: "Vert Émeraude", hex: "#063D2E" },
  { name: "Or Impérial", hex: "#D4AF62" },
  { name: "Bleu Marine", hex: "#00205B" },
  { name: "Rouge Rubis", hex: "#C8102E" },
  { name: "Camel Doré", hex: "#C19A6B" },
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
    iconName: "shirt",
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
        options_csv: "Noir Onyx, Blanc Pur, Bordeaux Royal, Vert Émeraude, Bleu Marine, Rouge Rubis",
        rich_options: [
          { value: "Noir Onyx", label_fr: "Noir Onyx", color_hex: "#1A1A1A" },
          { value: "Blanc Pur", label_fr: "Blanc Pur", color_hex: "#FFFFFF" },
          { value: "Bordeaux Royal", label_fr: "Bordeaux Royal", color_hex: "#5B1E31" },
          { value: "Vert Émeraude", label_fr: "Vert Émeraude", color_hex: "#063D2E" },
          { value: "Bleu Marine", label_fr: "Bleu Marine", color_hex: "#00205B" },
          { value: "Rouge Rubis", label_fr: "Rouge Rubis", color_hex: "#C8102E" },
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
    iconName: "shoes",
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
    iconName: "bag",
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
    iconName: "watch",
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
    ],
  },
  {
    id: "beaute",
    name: "Cosmétiques & Parfumerie",
    iconName: "gem",
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
    iconName: "glasses",
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
    ],
  },
];

export function CategoryBuilderPage({ onCategoryChanged }: { onCategoryChanged?: () => void }) {
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusMsg, setStatusMsg] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | "active" | "homepage" | "with_attrs">("all");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [activePresetId, setActivePresetId] = useState<string | null>(null);

  // New Category Creation Drafts
  const [nameFr, setNameFr] = useState(() => readDraft("luxe_cat_draft_name_fr", ""));
  const [nameAr, setNameAr] = useState(() => readDraft("luxe_cat_draft_name_ar", ""));
  const [nameEn, setNameEn] = useState(() => readDraft("luxe_cat_draft_name_en", ""));
  const [slug, setSlug] = useState(() => readDraft("luxe_cat_draft_slug", ""));
  const [descriptionFr, setDescriptionFr] = useState(() => readDraft("luxe_cat_draft_desc", ""));
  const [displayOrder, setDisplayOrder] = useState(() => readDraft("luxe_cat_draft_order", 10));
  const [imageUrl, setImageUrl] = useState(() => readDraft("luxe_cat_draft_img", "/assets/cat_sacs.jpg"));
  const [bannerUrl, setBannerUrl] = useState(() => readDraft("luxe_cat_draft_banner", "/assets/hero_bag_clean.jpg"));
  const [chosenIconKey, setChosenIconKey] = useState("shirt");

  useEffect(() => {
    writeDraft("luxe_cat_draft_name_fr", nameFr);
    writeDraft("luxe_cat_draft_name_ar", nameAr);
    writeDraft("luxe_cat_draft_name_en", nameEn);
    writeDraft("luxe_cat_draft_slug", slug);
    writeDraft("luxe_cat_draft_desc", descriptionFr);
    writeDraft("luxe_cat_draft_order", displayOrder);
    writeDraft("luxe_cat_draft_img", imageUrl);
    writeDraft("luxe_cat_draft_banner", bannerUrl);
  }, [nameFr, nameAr, nameEn, slug, descriptionFr, displayOrder, imageUrl, bannerUrl]);

  const [attributes, setAttributes] = useState<DraftAttribute[]>(() =>
    readDraft("luxe_cat_draft_attrs", CATEGORY_PRESETS[0].attributes)
  );

  useEffect(() => {
    writeDraft("luxe_cat_draft_attrs", attributes);
  }, [attributes]);

  // New attribute draft inputs (for creation form)
  const [newKey, setNewKey] = useState("");
  const [newLabelFr, setNewLabelFr] = useState("");
  const [newType, setNewType] = useState("color");
  const [newUnit, setNewUnit] = useState("");
  const [newRequired, setNewRequired] = useState(true);
  const [newFilterable, setNewFilterable] = useState(true);
  const [newVariantAxis, setNewVariantAxis] = useState(true);
  const [newOptionsCsv, setNewOptionsCsv] = useState("");
  const [richOptionsDraft, setRichOptionsDraft] = useState<OptionDetail[]>([]);
  const [newColorHex, setNewColorHex] = useState("#1A1A1A");
  const [newColorName, setNewColorName] = useState("");
  const [newSizeValue, setNewSizeValue] = useState("");

  // Edit Modal State
  const [editingCategory, setEditingCategory] = useState<any | null>(null);
  const [editNameFr, setEditNameFr] = useState("");
  const [editNameAr, setEditNameAr] = useState("");
  const [editNameEn, setEditNameEn] = useState("");
  const [editSlug, setEditSlug] = useState("");
  const [editDescFr, setEditDescFr] = useState("");
  const [editOrder, setEditOrder] = useState(1);
  const [editShowHomepage, setEditShowHomepage] = useState(true);
  const [editIsActive, setEditIsActive] = useState(true);
  const [editIconKey, setEditIconKey] = useState("bag");
  const [savingEdit, setSavingEdit] = useState(false);

  // Delete / Archive Modal State
  const [deletingCategory, setDeletingCategory] = useState<any | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Quick Add Attribute to Existing Category Modal State
  const [quickAttrCategory, setQuickAttrCategory] = useState<any | null>(null);
  const [quickAttrKey, setQuickAttrKey] = useState("");
  const [quickAttrLabelFr, setQuickAttrLabelFr] = useState("");
  const [quickAttrType, setQuickAttrType] = useState("short_text");
  const [quickAttrOptionsCsv, setQuickAttrOptionsCsv] = useState("");
  const [quickAttrRequired, setQuickAttrRequired] = useState(false);
  const [quickAttrFilterable, setQuickAttrFilterable] = useState(true);
  const [quickAttrVariantAxis, setQuickAttrVariantAxis] = useState(false);
  const [quickAttrUnit, setQuickAttrUnit] = useState("");
  const [savingQuickAttr, setSavingQuickAttr] = useState(false);

  async function loadCategories() {
    setLoading(true);
    setError("");
    try {
      const res = await DesktopCmsApi.getCategories();
      const list = Array.isArray(res) ? res : res?.items || [];
      setCategories(list);
    } catch (err: any) {
      notifyClientError(err, "Chargement des catégories impossible");
      setError(err?.message || "Erreur lors du chargement des catégories.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCategories();
  }, []);

  function applyCategoryPreset(preset: CategoryPreset) {
    setActivePresetId(preset.id);
    setNameFr(preset.name_fr);
    setNameAr(preset.name_ar);
    setNameEn(preset.name_en);
    setSlug(preset.slug);
    setDescriptionFr(preset.description_fr);
    setImageUrl(preset.image_url);
    setBannerUrl(preset.banner_url);
    setChosenIconKey(preset.iconName);
    setAttributes([...preset.attributes]);
    setRichOptionsDraft([]);
    notifyClientSuccess(
      "Modèle appliqué",
      `Le modèle "${preset.name}" a configuré la catégorie et ses ${preset.attributes.length} attributs.`
    );
  }

  function addDraftColorOption(nameOverride?: string, hexOverride?: string) {
    const name = (nameOverride || newColorName).trim();
    const hex = (hexOverride || newColorHex).trim() || "#1A1A1A";
    if (!name) {
      notifyClientWarning("Nom de couleur requis", "Veuillez indiquer un nom pour cette nuance (ex: Vert Sauge).");
      return;
    }
    if (richOptionsDraft.some((o) => o.value.toLowerCase() === name.toLowerCase())) {
      notifyClientWarning("Couleur déjà présente", `La nuance "${name}" est déjà dans la liste.`);
      return;
    }
    setRichOptionsDraft((prev) => [...prev, { value: name, label_fr: name, color_hex: hex }]);
    setNewColorName("");
  }

  function addDraftSizeOption(sizeVal?: string) {
    const val = (sizeVal || newSizeValue).trim();
    if (!val) {
      notifyClientWarning("Taille requise", "Veuillez indiquer une valeur de taille ou pointure (ex: XL ou 42).");
      return;
    }
    if (richOptionsDraft.some((o) => o.value.toLowerCase() === val.toLowerCase())) {
      notifyClientWarning("Taille déjà présente", `La taille "${val}" figure déjà dans la liste.`);
      return;
    }
    setRichOptionsDraft((prev) => [...prev, { value: val, label_fr: val }]);
    setNewSizeValue("");
  }

  function applySizeGroupPreset(group: string[]) {
    const existing = new Set(richOptionsDraft.map((o) => o.value.toLowerCase()));
    const additions: OptionDetail[] = [];
    group.forEach((sz) => {
      if (!existing.has(sz.toLowerCase())) {
        additions.push({ value: sz, label_fr: sz });
      }
    });
    setRichOptionsDraft((prev) => [...prev, ...additions]);
    notifyClientSuccess("Groupe de tailles ajouté", `${additions.length} taille(s) ajoutée(s).`);
  }

  function removeRichOption(val: string) {
    setRichOptionsDraft((prev) => prev.filter((o) => o.value !== val));
  }

  function addDraftAttribute() {
    const cleanKey = newKey.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_");
    if (!cleanKey || !newLabelFr.trim()) {
      notifyClientWarning(
        "Champs d'attribut incomplets",
        "Veuillez renseigner le code technique (ex: matiere) et le libellé en français avant d'ajouter l'attribut."
      );
      return;
    }
    if (attributes.some((a) => a.attr_key === cleanKey)) {
      notifyClientWarning(
        "Clé d'attribut déjà présente",
        `L'attribut "${cleanKey}" figure déjà dans la liste de cette catégorie.`
      );
      return;
    }

    let finalRich = richOptionsDraft.length ? richOptionsDraft : undefined;
    let finalCsv = newOptionsCsv.trim();

    if (finalRich && finalRich.length > 0) {
      finalCsv = finalRich.map((o) => o.value).join(", ");
    } else if (finalCsv) {
      finalRich = finalCsv
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((v) => ({ value: v, label_fr: v }));
    }

    setAttributes((prev) => [
      ...prev,
      {
        attr_key: cleanKey,
        label_fr: newLabelFr.trim(),
        label_ar: (newLabelFr).trim(),
        label_en: (newLabelFr).trim(),
        input_type: newType,
        unit: newUnit.trim(),
        is_required: newRequired,
        is_filterable: newFilterable,
        is_variant_axis: newVariantAxis,
        options_csv: finalCsv,
        rich_options: finalRich,
      },
    ]);

    setNewKey("");
    setNewLabelFr("");
    setNewOptionsCsv("");
    setRichOptionsDraft([]);
    notifyClientSuccess("Attribut ajouté au modèle", `L'attribut "${newLabelFr.trim()}" (${cleanKey}) a été configuré.`);
  }

  function removeDraftAttribute(idx: number) {
    setAttributes((prev) => prev.filter((_, i) => i !== idx));
  }

  function moveAttributeUp(idx: number) {
    if (idx <= 0) return;
    setAttributes((prev) => {
      const copy = [...prev];
      const temp = copy[idx - 1];
      copy[idx - 1] = copy[idx];
      copy[idx] = temp;
      return copy;
    });
  }

  function moveAttributeDown(idx: number) {
    if (idx >= attributes.length - 1) return;
    setAttributes((prev) => {
      const copy = [...prev];
      const temp = copy[idx + 1];
      copy[idx + 1] = copy[idx];
      copy[idx] = temp;
      return copy;
    });
  }

  async function handleSaveCategory(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setStatusMsg("");
    if (nameFr.trim().length < 2 || slug.trim().length < 2) {
      notifyClientWarning(
        "Informations de catégorie incomplètes",
        "Veuillez indiquer un nom en français et un identifiant URL (slug) d'au moins 2 caractères."
      );
      return;
    }
    try {
      const created = await DesktopCmsApi.createCategory({
        slug: slug.trim().toLowerCase(),
        name_fr: nameFr.trim(),
        name_ar: (nameAr || nameFr).trim(),
        name_en: (nameEn || nameFr).trim(),
        description_fr: descriptionFr.trim(),
        image_url: imageUrl || "/assets/cat_sacs.jpg",
        banner_url: bannerUrl || "/assets/hero_bag_clean.jpg",
        display_order: Number(displayOrder) || 10,
        is_active: true,
        show_on_homepage: true,
      });

      for (let i = 0; i < attributes.length; i++) {
        const attr = attributes[i];
        let optionsPayload: any[] = [];
        if (attr.rich_options && attr.rich_options.length > 0) {
          optionsPayload = attr.rich_options.map((opt, idx) => ({
            value: opt.value,
            label_fr: opt.label_fr || opt.value,
            label_ar: opt.label_ar || opt.value,
            label_en: opt.label_en || opt.value,
            color_hex: opt.color_hex || null,
            display_order: idx + 1,
          }));
        } else {
          optionsPayload = (attr.options_csv || "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
            .map((val, idx) => ({
              value: val,
              label_fr: val,
              label_ar: val,
              label_en: val,
              color_hex: null,
              display_order: idx + 1,
            }));
        }

        await DesktopCmsApi.addCategoryAttribute({
          category_id: created.id,
          attr_key: attr.attr_key,
          label_fr: attr.label_fr,
          label_ar: attr.label_ar || attr.label_fr,
          label_en: attr.label_en || attr.label_fr,
          input_type: attr.input_type,
          unit: attr.unit,
          is_required: attr.is_required,
          is_filterable: attr.is_filterable,
          is_variant_axis: attr.is_variant_axis,
          display_order: i + 1,
          options: optionsPayload,
        });
      }

      const okMsg = `Catégorie "${nameFr}" et ses ${attributes.length} attribut(s) enregistrés avec succès.`;
      setStatusMsg(okMsg);
      notifyClientSuccess("Catégorie créée avec succès", okMsg);
      setNameFr("");
      setNameAr("");
      setNameEn("");
      setSlug("");
      setDescriptionFr("");
      clearDraft("luxe_cat_draft_name_fr");
      clearDraft("luxe_cat_draft_name_ar");
      clearDraft("luxe_cat_draft_name_en");
      clearDraft("luxe_cat_draft_slug");
      clearDraft("luxe_cat_draft_desc");
      setShowCreateForm(false);
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, "Création de la catégorie impossible");
      setError(tr.message);
    }
  }

'''

print("Component top and logic ready.")
