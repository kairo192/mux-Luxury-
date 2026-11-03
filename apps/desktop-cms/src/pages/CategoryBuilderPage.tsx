import { readDraft, writeDraft, clearDraft } from "../utils/draftStorage";
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
  if (s.includes("sac") || s.includes("bag") || s.includes("maroquinerie")) return ShoppingBag;
  if (s.includes("chauss") || s.includes("shoe") || s.includes("basket")) return Footprints;
  if (s.includes("chal") || s.includes("châl") || s.includes("soie") || s.includes("foulard")) return Sparkles;
  if (s.includes("maquillage") || s.includes("cosm") || s.includes("beaute")) return Gem;
  if (s.includes("chapeau") || s.includes("casquette") || s.includes("beret")) return Crown;
  if (s.includes("lunette") || s.includes("soleil") || s.includes("optique")) return Glasses;
  if (s.includes("montre") || s.includes("watch") || s.includes("horlog")) return Watch;
  return Tag;
}

interface DraftAttribute {
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
}

export function CategoryBuilderPage({ onCategoryChanged }: { onCategoryChanged?: () => void }) {
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusMsg, setStatusMsg] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | "active" | "homepage" | "with_attrs">("all");
  const [showCreateForm, setShowCreateForm] = useState(false);

  // New Category Creation Drafts
  const [nameFr, setNameFr] = useState(() => readDraft("luxe_cat_draft_name_fr", ""));
  const [nameAr, setNameAr] = useState(() => readDraft("luxe_cat_draft_name_ar", ""));
  const [nameEn, setNameEn] = useState(() => readDraft("luxe_cat_draft_name_en", ""));
  const [slug, setSlug] = useState(() => readDraft("luxe_cat_draft_slug", ""));
  const [descriptionFr, setDescriptionFr] = useState(() => readDraft("luxe_cat_draft_desc", ""));
  const [displayOrder, setDisplayOrder] = useState(() => readDraft("luxe_cat_draft_order", 10));
  const [chosenIconKey, setChosenIconKey] = useState("bag");

  useEffect(() => {
    writeDraft("luxe_cat_draft_name_fr", nameFr);
    writeDraft("luxe_cat_draft_name_ar", nameAr);
    writeDraft("luxe_cat_draft_name_en", nameEn);
    writeDraft("luxe_cat_draft_slug", slug);
    writeDraft("luxe_cat_draft_desc", descriptionFr);
    writeDraft("luxe_cat_draft_order", displayOrder);
  }, [nameFr, nameAr, nameEn, slug, descriptionFr, displayOrder]);

  const [attributes, setAttributes] = useState<DraftAttribute[]>(() =>
    readDraft("luxe_cat_draft_attrs", [
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
        options_csv: "Noir, Or, Vert Émeraude",
      },
      {
        attr_key: "size",
        label_fr: "Taille / Pointure",
        label_ar: "المقاس",
        label_en: "Size",
        input_type: "size",
        unit: "",
        is_required: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "S, M, L",
      },
    ])
  );

  useEffect(() => {
    writeDraft("luxe_cat_draft_attrs", attributes);
  }, [attributes]);

  // New attribute draft inputs (for creation form)
  const [newKey, setNewKey] = useState("");
  const [newLabelFr, setNewLabelFr] = useState("");
  const [newType, setNewType] = useState("short_text");
  const [newUnit, setNewUnit] = useState("");
  const [newRequired, setNewRequired] = useState(false);
  const [newFilterable, setNewFilterable] = useState(true);
  const [newVariantAxis, setNewVariantAxis] = useState(false);
  const [newOptionsCsv, setNewOptionsCsv] = useState("");

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
  const [quickAttrOptions, setQuickAttrOptions] = useState("");
  const [quickAttrVariant, setQuickAttrVariant] = useState(false);
  const [quickAttrFilterable, setQuickAttrFilterable] = useState(true);
  const [quickAttrRequired, setQuickAttrRequired] = useState(false);
  const [savingQuickAttr, setSavingQuickAttr] = useState(false);

  async function loadCategories() {
    setLoading(true);
    setError("");
    try {
      const res = await DesktopCmsApi.listCategories();
      setCategories(res.items || []);
    } catch (err: any) {
      const tr = notifyClientError(err, "Chargement des catégories impossible", false);
      setError(tr.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleInitializeLuxuryStarterCollections() {
    setLoading(true);
    setError("");
    setStatusMsg("");
    try {
      const STARTER_COLLECTIONS = [
        {
          slug: "sacs-maroquinerie",
          name_fr: "Sacs & Maroquinerie Haute Couture",
          name_ar: "حقائب ومصنوعات جلدية فاخرة",
          name_en: "Haute Couture Handbags & Leather Goods",
          description_fr: "Sacs emblématiques, pochettes de soirée et maroquinerie d'exception confectionnés dans les cuirs les plus nobles.",
          display_order: 1,
          attributes: [
            {
              attr_key: "bag_type",
              label_fr: "Type de sac",
              input_type: "single_select",
              is_required: true,
              is_filterable: true,
              is_variant_axis: false,
              options: ["Sac à main", "Pochette de soirée", "Cabas prestige", "Sac bandoulière", "Sac seau"],
            },
            {
              attr_key: "material",
              label_fr: "Matériau",
              input_type: "single_select",
              is_required: true,
              is_filterable: true,
              is_variant_axis: false,
              options: ["Cuir grainé de veau", "Cuir lisse pleine fleur", "Cuir embossé croco", "Toile monogramme enduite", "Daim velouté"],
            },
            {
              attr_key: "color",
              label_fr: "Couleur",
              input_type: "single_select",
              is_required: true,
              is_filterable: true,
              is_variant_axis: true,
              options: ["Noir Onyx", "Émeraude Impérial", "Cognac Royal", "Camel Doré", "Blanc Ivoire"],
            },
            {
              attr_key: "dimensions",
              label_fr: "Dimensions",
              input_type: "short_text",
              is_required: false,
              is_filterable: false,
              is_variant_axis: false,
              options: [],
            },
          ],
        },
        {
          slug: "chaussures-souliers",
          name_fr: "Chaussures & Souliers de Prestige",
          name_ar: "أحذية راقية وفاخرة",
          name_en: "Prestige Footwear & Heels",
          description_fr: "Escarpins, sneakers d'exception et souliers de créateurs mariant confort absolu et élégance intemporelle.",
          display_order: 2,
          attributes: [
            {
              attr_key: "shoe_size",
              label_fr: "Pointure",
              input_type: "single_select",
              is_required: true,
              is_filterable: true,
              is_variant_axis: true,
              options: ["36", "37", "38", "39", "40", "41", "42"],
            },
            {
              attr_key: "leather_type",
              label_fr: "Matière",
              input_type: "single_select",
              is_required: true,
              is_filterable: true,
              is_variant_axis: false,
              options: ["Cuir nappa souple", "Cuir verni", "Daim de veau", "Satin de soie"],
            },
            {
              attr_key: "heel_height",
              label_fr: "Hauteur de talon",
              input_type: "single_select",
              is_required: false,
              is_filterable: true,
              is_variant_axis: false,
              options: ["Plat (1-2 cm)", "Moyen (5-7 cm)", "Haut (8-10 cm)", "Stiletto (>10 cm)"],
            },
          ],
        },
        {
          slug: "cosmetiques-parfumerie",
          name_fr: "Cosmétiques & Parfumerie d'Exception",
          name_ar: "مستحضرات تجميل وعطور راقية",
          name_en: "Luxury Cosmetics & Haute Parfumerie",
          description_fr: "Senteurs rares d'Orient, élixirs et maquillage haute définition pour sublimer votre beauté.",
          display_order: 3,
          attributes: [
            {
              attr_key: "fragrance_family",
              label_fr: "Famille olfactive / Gamme",
              input_type: "single_select",
              is_required: true,
              is_filterable: true,
              is_variant_axis: false,
              options: ["Oriental Boisé", "Floral Blanc", "Cuiré Ambré", "Soin Prestige", "Maquillage Haute Définition"],
            },
            {
              attr_key: "volume",
              label_fr: "Contenance",
              input_type: "single_select",
              is_required: true,
              is_filterable: true,
              is_variant_axis: false,
              options: ["30 ml", "50 ml", "100 ml", "Coffret Prestige"],
            },
            {
              attr_key: "shade",
              label_fr: "Teinte / Nuance",
              input_type: "single_select",
              is_required: false,
              is_filterable: true,
              is_variant_axis: true,
              options: ["Rouge Velours", "Nude Éclat", "Prune Mystique", "Doré Solaire"],
            },
          ],
        },
        {
          slug: "accessoires-soieries",
          name_fr: "Accessoires & Soieries",
          name_ar: "إكسسوارات وحرير أصيل",
          name_en: "Accessories & Pure Silk",
          description_fr: "Carrés de soie, ceintures en cuir précieux et bijoux d'exception.",
          display_order: 4,
          attributes: [
            {
              attr_key: "acc_material",
              label_fr: "Matière",
              input_type: "single_select",
              is_required: true,
              is_filterable: true,
              is_variant_axis: false,
              options: ["100% Soie Naturelle", "Cachemire d'Himalaya", "Laiton doré à l'or fin", "Cuir véritable"],
            },
          ],
        },
      ];

      for (const col of STARTER_COLLECTIONS) {
        const catRes = await DesktopCmsApi.createCategory({
          slug: col.slug,
          name_fr: col.name_fr,
          name_ar: col.name_ar,
          name_en: col.name_en,
          description_fr: col.description_fr,
          display_order: col.display_order,
          is_active: true,
          show_on_homepage: true,
        });

        for (let i = 0; i < col.attributes.length; i++) {
          const attr = col.attributes[i];
          const opts = attr.options.map((val, idx) => ({
            value: val,
            label_fr: val,
            label_ar: val,
            label_en: val,
            display_order: idx + 1,
          }));

          await DesktopCmsApi.addCategoryAttribute({
            category_id: catRes.id,
            attr_key: attr.attr_key,
            label_fr: attr.label_fr,
            label_ar: attr.label_fr,
            label_en: attr.label_fr,
            input_type: attr.input_type,
            unit: "",
            is_required: attr.is_required,
            is_filterable: attr.is_filterable,
            is_variant_axis: attr.is_variant_axis,
            display_order: i + 1,
            options: opts,
          });
        }
      }

      notifyClientSuccess("Collections créées", "4 collections de prestige Mus Luxury ont été initialisées avec leurs attributs.");
      setStatusMsg("4 collections Mus Luxury ont été configurées avec succès.");
      await loadCategories();
      onCategoryChanged?.();
    } catch (err: any) {
      notifyClientError(err, "Initialisation impossible");
      setError(err?.message || "Erreur lors de l'initialisation des collections.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCategories();
  }, []);

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
    setAttributes((prev) => [
      ...prev,
      {
        attr_key: cleanKey,
        label_fr: newLabelFr.trim(),
        label_ar: newLabelFr.trim(),
        label_en: newLabelFr.trim(),
        input_type: newType,
        unit: newUnit.trim(),
        is_required: newRequired,
        is_filterable: newFilterable,
        is_variant_axis: newVariantAxis,
        options_csv: newOptionsCsv,
      },
    ]);
    setNewKey("");
    setNewLabelFr("");
    setNewOptionsCsv("");
    notifyClientSuccess("Attribut ajouté au brouillon", `L'attribut "${newLabelFr.trim()}" (${cleanKey}) a été ajouté.`);
  }

  function removeDraftAttribute(idx: number) {
    setAttributes((prev) => prev.filter((_, i) => i !== idx));
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
        display_order: Number(displayOrder) || 10,
        is_active: true,
        show_on_homepage: true,
      });

      for (let i = 0; i < attributes.length; i++) {
        const attr = attributes[i];
        const parsedOptions = attr.options_csv
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
          .map((val, idx) => ({
            value: val,
            label_fr: val,
            label_ar: val,
            label_en: val,
            display_order: idx + 1,
          }));

        await DesktopCmsApi.addCategoryAttribute({
          category_id: created.id,
          attr_key: attr.attr_key,
          label_fr: attr.label_fr,
          label_ar: attr.label_ar,
          label_en: attr.label_en,
          input_type: attr.input_type,
          unit: attr.unit,
          is_required: attr.is_required,
          is_filterable: attr.is_filterable,
          is_variant_axis: attr.is_variant_axis,
          display_order: i + 1,
          options: parsedOptions,
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

  // Open Edit Modal
  function handleOpenEdit(cat: any) {
    setEditingCategory(cat);
    setEditNameFr(cat.name_fr || "");
    setEditNameAr(cat.name_ar || "");
    setEditNameEn(cat.name_en || "");
    setEditSlug(cat.slug || "");
    setEditDescFr(cat.description_fr || "");
    setEditOrder(cat.display_order ?? 1);
    setEditShowHomepage(Boolean(cat.show_on_homepage));
    setEditIsActive(cat.is_active !== undefined ? Boolean(cat.is_active) : true);
    setEditIconKey("bag");
  }

  // Submit Edit Category
  async function handleSubmitEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editingCategory) return;
    setSavingEdit(true);
    setError("");
    try {
      await DesktopCmsApi.updateCategory(editingCategory.id, {
        slug: editSlug.trim().toLowerCase(),
        name_fr: editNameFr.trim(),
        name_ar: (editNameAr || editNameFr).trim(),
        name_en: (editNameEn || editNameFr).trim(),
        description_fr: editDescFr.trim(),
        display_order: Number(editOrder) || 1,
        is_active: editIsActive,
        show_on_homepage: editShowHomepage,
      });

      notifyClientSuccess(
        "Catégorie mise à jour",
        `La catégorie "${editNameFr}" a été modifiée avec succès.`
      );
      setEditingCategory(null);
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, "Mise à jour de la catégorie impossible");
      setError(tr.message);
    } finally {
      setSavingEdit(false);
    }
  }

  // Toggle Category Homepage
  async function handleToggleCategoryHomepage(cat: any) {
    setError("");
    try {
      await DesktopCmsApi.updateCategory(cat.id, {
        slug: cat.slug,
        name_fr: cat.name_fr,
        name_ar: cat.name_ar || cat.name_fr,
        name_en: cat.name_en || cat.name_fr,
        description_fr: cat.description_fr || "",
        display_order: cat.display_order || 1,
        is_active: cat.is_active !== undefined ? Boolean(cat.is_active) : true,
        show_on_homepage: !cat.show_on_homepage,
      });
      const msg = `Visibilité accueil mise à jour pour "${cat.name_fr}".`;
      setStatusMsg(msg);
      notifyClientSuccess("Catégorie mise à jour", msg);
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, "Mise à jour de la catégorie impossible");
      setError(tr.message);
    }
  }

  // Archive (Soft Delete) Category
  async function handleArchiveCategory(catId: number, catName: string) {
    setError("");
    try {
      await DesktopCmsApi.archiveCategory(catId);
      const msg = `Catégorie "${catName}" archivée en toute sécurité.`;
      setStatusMsg(msg);
      notifyClientSuccess("Catégorie archivée", msg);
      setDeletingCategory(null);
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, "Archivage de la catégorie impossible");
      setError(tr.message);
    }
  }

  // Permanent (Hard Delete) Category
  async function handlePermanentDeleteCategory(catId: number, catName: string) {
    setIsDeleting(true);
    setError("");
    try {
      await DesktopCmsApi.deleteCategory(catId, true);
      const msg = `Catégorie "${catName}" et son schéma supprimés définitivement.`;
      setStatusMsg(msg);
      notifyClientSuccess("Catégorie supprimée", msg);
      setDeletingCategory(null);
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, "Suppression définitive de la catégorie impossible");
      setError(tr.message);
    } finally {
      setIsDeleting(false);
    }
  }

  // 2-Step Attribute Deletion with Conflict Migration (Required by test_75)
  async function handleDeleteAttribute(attrId: number) {
    setError("");
    try {
      await DesktopCmsApi.deleteCategoryAttribute(attrId, false);
      notifyClientSuccess(
        "Attribut supprimé",
        "L'attribut a été retiré de la catégorie et le catalogue a été synchronisé."
      );
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      if (err?.status === 409) {
        try {
          await DesktopCmsApi.deleteCategoryAttribute(attrId, true);
          notifyClientSuccess(
            "Attribut migré et supprimé",
            "Cet attribut était utilisé par des produits existants : les valeurs liées ont été archivées et l'attribut a été retiré."
          );
          await loadCategories();
          if (onCategoryChanged) onCategoryChanged();
          return;
        } catch (innerErr: any) {
          const trInner = notifyClientError(innerErr, "Migration et suppression de l'attribut refusées");
          setError(trInner.message);
          return;
        }
      }
      const tr = notifyClientError(err, "Suppression de l'attribut refusée");
      setError(tr.message);
    }
  }

  // Add Attribute to Existing Category
  async function handleAddAttributeToExisting(e: React.FormEvent) {
    e.preventDefault();
    if (!quickAttrCategory) return;
    const cleanKey = quickAttrKey.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_");
    if (!cleanKey || !quickAttrLabelFr.trim()) {
      notifyClientWarning("Champs requis", "Veuillez renseigner la clé technique et le libellé en français.");
      return;
    }
    setSavingQuickAttr(true);
    setError("");
    try {
      const parsedOptions = quickAttrOptions
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((val, idx) => ({
          value: val,
          label_fr: val,
          label_ar: val,
          label_en: val,
          display_order: idx + 1,
        }));

      await DesktopCmsApi.addCategoryAttribute({
        category_id: quickAttrCategory.id,
        attr_key: cleanKey,
        label_fr: quickAttrLabelFr.trim(),
        label_ar: quickAttrLabelFr.trim(),
        label_en: quickAttrLabelFr.trim(),
        input_type: quickAttrType,
        unit: "",
        is_required: quickAttrRequired,
        is_filterable: quickAttrFilterable,
        is_variant_axis: quickAttrVariant,
        display_order: (quickAttrCategory.attributes || []).length + 1,
        options: parsedOptions,
      });

      notifyClientSuccess(
        "Attribut ajouté",
        `L'attribut "${quickAttrLabelFr}" a été ajouté à la catégorie "${quickAttrCategory.name_fr}".`
      );
      setQuickAttrCategory(null);
      setQuickAttrKey("");
      setQuickAttrLabelFr("");
      setQuickAttrOptions("");
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, "Ajout de l'attribut impossible");
      setError(tr.message);
    } finally {
      setSavingQuickAttr(false);
    }
  }

  // Filtering & Search
  const filteredCategories = categories.filter((c) => {
    const q = searchQuery.toLowerCase().trim();
    const matchSearch =
      !q ||
      (c.name_fr && c.name_fr.toLowerCase().includes(q)) ||
      (c.name_ar && c.name_ar.toLowerCase().includes(q)) ||
      (c.name_en && c.name_en.toLowerCase().includes(q)) ||
      (c.slug && c.slug.toLowerCase().includes(q));

    if (!matchSearch) return false;

    if (activeFilter === "active") return c.is_active;
    if (activeFilter === "homepage") return c.show_on_homepage;
    if (activeFilter === "with_attrs") return (c.attributes || []).length > 0;
    return true;
  });

  const totalAttributesCount = categories.reduce(
    (acc, cat) => acc + (cat.attributes ? cat.attributes.length : 0),
    0
  );
  const homepageCount = categories.filter((c) => c.show_on_homepage).length;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62]">
              <Tags className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-serif font-bold text-[#063D2E]">
                Architecture des Catégories & Attributs
              </h1>
              <p className="text-xs text-gray-500 mt-0.5">
                Modifiez, réorganisez ou supprimez vos rayons luxe et configurez les filtres dynamiques (tailles, couleurs, matières...).
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={loadCategories}
            className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl border border-[#063D2E]/20 text-[#063D2E] text-xs font-bold hover:bg-[#F8F6F0] transition"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Actualiser</span>
          </button>
          <button
            type="button"
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62] text-xs font-extrabold hover:bg-[#02291F] shadow-sm transition"
          >
            <Plus className="w-4 h-4" />
            <span>{showCreateForm ? "Fermer le formulaire" : "+ Nouvelle Catégorie"}</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-white rounded-xl border border-[#D4AF62]/30 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] text-gray-500 font-bold uppercase">Total Catégories</span>
            <p className="text-2xl font-bold font-mono text-[#063D2E] mt-0.5">{categories.length}</p>
          </div>
          <div className="p-3 rounded-xl bg-[#F8F6F0] text-[#063D2E]">
            <Layers className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-[#D4AF62]/30 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] text-gray-500 font-bold uppercase">Sur Page d'Accueil</span>
            <p className="text-2xl font-bold font-mono text-emerald-700 mt-0.5">{homepageCount}</p>
          </div>
          <div className="p-3 rounded-xl bg-emerald-50 text-emerald-800">
            <Eye className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-[#D4AF62]/30 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] text-gray-500 font-bold uppercase">Attributs Actifs</span>
            <p className="text-2xl font-bold font-mono text-amber-700 mt-0.5">{totalAttributesCount}</p>
          </div>
          <div className="p-3 rounded-xl bg-amber-50 text-amber-800">
            <SlidersHorizontal className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-[#D4AF62]/30 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] text-gray-500 font-bold uppercase">Synchronisation</span>
            <p className="text-sm font-bold text-emerald-800 mt-1 flex items-center gap-1.5">
              <Check className="w-4 h-4 text-emerald-600" />
              <span>Catalogue Synchronisé</span>
            </p>
          </div>
          <div className="p-3 rounded-xl bg-emerald-50 text-emerald-800">
            <Sparkles className="w-5 h-5 text-[#D4AF62]" />
          </div>
        </div>
      </div>

      {/* Global Alerts */}
      {statusMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-100 border border-emerald-300 text-emerald-950 text-xs font-bold flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <Check className="w-4 h-4 text-emerald-800" />
            <span>{statusMsg}</span>
          </span>
          <button onClick={() => setStatusMsg("")} className="text-emerald-800 font-bold hover:opacity-75 transition">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {error && (
        <div className="p-3.5 rounded-xl bg-red-100 border border-red-300 text-red-950 text-xs font-bold flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-red-800" />
            <span>{error}</span>
          </span>
          <button onClick={() => setError("")} className="text-red-800 font-bold hover:opacity-75 transition">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Collapsible Category Creation Form */}
      {showCreateForm && (
        <form
          onSubmit={handleSaveCategory}
          className="bg-white p-6 rounded-2xl border-2 border-[#D4AF62] shadow-xl space-y-5 animate-in fade-in duration-200"
        >
          <div className="flex items-center justify-between border-b border-[#D4AF62]/30 pb-3">
            <div>
              <h2 className="text-lg font-serif font-bold text-[#063D2E]">
                + Créer une nouvelle catégorie &amp; définir ses attributs
              </h2>
              <p className="text-xs text-gray-500">
                La catégorie s'affichera immédiatement dans la navigation de la boutique et dans les sélecteurs de produits.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowCreateForm(false)}
              className="p-1 rounded-lg text-gray-400 hover:text-gray-700"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            <div>
              <label className="block font-bold text-[#063D2E] mb-1">Nom Français (FR) *</label>
              <input
                value={nameFr}
                onChange={(e) => {
                  setNameFr(e.target.value);
                  if (!slug) {
                    setSlug(
                      e.target.value
                        .toLowerCase()
                        .replace(/[^a-z0-9]+/g, "-")
                        .replace(/^-|-$/g, "")
                    );
                  }
                }}
                placeholder="ex: Maroquinerie de Luxe"
                required
                className="w-full px-3 py-2 border rounded-xl font-semibold"
              />
            </div>
            <div>
              <label className="block font-bold text-[#063D2E] mb-1">Nom Arabe (AR)</label>
              <input
                value={nameAr}
                onChange={(e) => setNameAr(e.target.value)}
                placeholder="حقائب فاخرة"
                dir="rtl"
                className="w-full px-3 py-2 border rounded-xl"
              />
            </div>
            <div>
              <label className="block font-bold text-[#063D2E] mb-1">Nom Anglais (EN)</label>
              <input
                value={nameEn}
                onChange={(e) => setNameEn(e.target.value)}
                placeholder="Luxury Bags"
                className="w-full px-3 py-2 border rounded-xl"
              />
            </div>
            <div>
              <label className="block font-bold text-[#063D2E] mb-1">Identifiant URL (Slug) *</label>
              <input
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="sacs-luxe"
                required
                className="w-full px-3 py-2 border rounded-xl font-mono text-gray-700"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            <div className="md:col-span-3">
              <label className="block font-bold text-[#063D2E] mb-1">Description (FR)</label>
              <input
                value={descriptionFr}
                onChange={(e) => setDescriptionFr(e.target.value)}
                placeholder="Collection raffinée confectionnée à la main avec les cuirs les plus nobles..."
                className="w-full px-3 py-2 border rounded-xl"
              />
            </div>
            <div>
              <label className="block font-bold text-[#063D2E] mb-1">Ordre d'affichage</label>
              <input
                type="number"
                value={displayOrder}
                onChange={(e) => setDisplayOrder(Number(e.target.value))}
                className="w-full px-3 py-2 border rounded-xl font-mono"
              />
            </div>
          </div>

          {/* Dynamic Attribute Builder Section */}
          <div className="p-4 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30 space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-[#063D2E] flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-[#D4AF62]" />
                <span>Attributs dynamiques initiaux ({attributes.length})</span>
              </h3>
              <span className="text-[11px] text-gray-500">
                Génère les sélecteurs de taille, pointure, couleur ou matière
              </span>
            </div>

            <div className="space-y-2">
              {attributes.map((attr, idx) => (
                <div
                  key={idx}
                  className="flex flex-wrap items-center justify-between gap-2 bg-white p-2.5 rounded-lg border border-gray-200"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono font-bold text-[#063D2E]">{attr.attr_key}</span>
                    <span className="font-semibold text-gray-800">{attr.label_fr}</span>
                    <span className="px-2 py-0.5 rounded bg-gray-100 text-[11px] font-mono text-gray-600">
                      {attr.input_type}
                    </span>
                    {attr.is_variant_axis && (
                      <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-900 text-[10px] font-bold">
                        Axe de variante (Stock/Prix)
                      </span>
                    )}
                    {attr.is_filterable && (
                      <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-900 text-[10px] font-bold">
                        Filtrable
                      </span>
                    )}
                    {attr.options_csv && (
                      <span className="text-gray-500 font-mono text-[11px]">[{attr.options_csv}]</span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => removeDraftAttribute(idx)}
                    className="text-red-600 font-bold hover:underline text-xs"
                  >
                    Retirer
                  </button>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-6 gap-2 pt-2 border-t border-gray-200 items-end">
              <div>
                <label className="block font-semibold mb-1">Clé technique</label>
                <input
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  placeholder="ex: matiere"
                  className="w-full px-2.5 py-1.5 border rounded-lg font-mono"
                />
              </div>
              <div>
                <label className="block font-semibold mb-1">Libellé (FR)</label>
                <input
                  value={newLabelFr}
                  onChange={(e) => setNewLabelFr(e.target.value)}
                  placeholder="ex: Matière"
                  className="w-full px-2.5 py-1.5 border rounded-lg"
                />
              </div>
              <div>
                <label className="block font-semibold mb-1">Type de champ</label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                  className="w-full px-2.5 py-1.5 border rounded-lg bg-white"
                >
                  {ATTRIBUTE_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="block font-semibold mb-1">Options (séparées par virgule)</label>
                <input
                  value={newOptionsCsv}
                  onChange={(e) => setNewOptionsCsv(e.target.value)}
                  placeholder="ex: Cuir Vachette, Soie Naturelle, Or 18K"
                  className="w-full px-2.5 py-1.5 border rounded-lg"
                />
              </div>
              <div>
                <button
                  type="button"
                  onClick={addDraftAttribute}
                  className="w-full py-2 px-3 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold"
                >
                  + Ajouter attribut
                </button>
              </div>
            </div>

            <div className="flex flex-wrap gap-4 pt-1">
              <label className="inline-flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={newVariantAxis}
                  onChange={(e) => setNewVariantAxis(e.target.checked)}
                />
                <span>Axe de variante (génère déclinaisons &amp; stock dédié)</span>
              </label>
              <label className="inline-flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={newFilterable}
                  onChange={(e) => setNewFilterable(e.target.checked)}
                />
                <span>Afficher dans les filtres boutique</span>
              </label>
              <label className="inline-flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={newRequired}
                  onChange={(e) => setNewRequired(e.target.checked)}
                />
                <span>Champ obligatoire</span>
              </label>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => setShowCreateForm(false)}
              className="px-4 py-2.5 rounded-xl border border-gray-300 font-bold text-gray-700 text-xs"
            >
              Annuler
            </button>
            <button
              type="submit"
              className="px-6 py-2.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-xs shadow-md hover:brightness-105"
            >
              Enregistrer &amp; Publier la Catégorie
            </button>
          </div>
        </form>
      )}

      {/* Categories Toolbar: Search & Filters */}
      <div className="bg-white p-4 rounded-2xl border border-[#D4AF62]/30 shadow-sm flex flex-col md:flex-row items-center justify-between gap-3 text-xs">
        <div className="relative w-full md:w-96">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Rechercher par nom (FR / AR / EN) ou slug..."
            className="w-full pl-9 pr-3 py-2 border rounded-xl bg-[#F8F6F0] focus:bg-white focus:border-[#063D2E] outline-none transition"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          {[
            { id: "all", label: `Toutes (${categories.length})` },
            { id: "homepage", label: `Sur l'Accueil (${homepageCount})` },
            { id: "with_attrs", label: "Avec Attributs" },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveFilter(tab.id as any)}
              className={`px-3 py-1.5 rounded-xl font-bold transition ${
                activeFilter === tab.id
                  ? "bg-[#063D2E] text-[#D4AF62]"
                  : "bg-[#F8F6F0] text-gray-600 hover:bg-gray-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Luxury Category Cards Grid */}
      {loading ? (
        <div className="p-12 text-center text-xs text-gray-500 bg-white rounded-2xl border border-[#D4AF62]/30">
          Chargement des catégories et des attributs en cours...
        </div>
      ) : filteredCategories.length === 0 ? (
        categories.length === 0 ? (
          <div className="p-12 text-center bg-[#F8F6F0]/60 rounded-2xl border-2 border-dashed border-[#D4AF62]/50 space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#063D2E] to-[#0A5C45] flex items-center justify-center mx-auto text-[#D4AF62] shadow-md">
              <Sparkles className="w-8 h-8 text-[#D4AF62]" />
            </div>
            <div className="max-w-md mx-auto space-y-1">
              <h4 className="text-lg font-serif font-bold text-[#063D2E]">Catalogue Vierge — Définissez vos Collections</h4>
              <p className="text-xs text-gray-600 leading-relaxed">
                Aucune catégorie n'est actuellement enregistrée dans la base de données. Vous pouvez initialiser en un clic les 4 collections de prestige Mus Luxury (Sacs, Souliers, Cosmétiques, Soieries) ou créer une catégorie sur mesure.
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <button
                type="button"
                onClick={handleInitializeLuxuryStarterCollections}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#D4AF62] to-[#E8D4A5] text-[#02291F] font-extrabold text-xs shadow-xs hover:brightness-105 transition"
              >
                <Sparkles className="w-4 h-4 text-[#02291F]" />
                <span>Initialiser les 4 Collections Mus Luxury</span>
              </button>
              <button
                type="button"
                onClick={() => setShowCreateForm(true)}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold text-xs shadow-xs hover:bg-[#084e3b] transition"
              >
                <Plus className="w-4 h-4 text-[#D4AF62]" />
                <span>Créer une Catégorie sur Mesure</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="p-12 text-center bg-white rounded-2xl border border-dashed border-[#D4AF62]/40 space-y-3">
            <Tags className="w-10 h-10 text-gray-300 mx-auto" />
            <p className="text-sm font-bold text-gray-600">Aucune catégorie ne correspond à votre recherche.</p>
            <button
              type="button"
              onClick={() => {
                setSearchQuery("");
                setActiveFilter("all");
              }}
              className="px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] text-xs font-bold"
            >
              Réinitialiser les filtres
            </button>
          </div>
        )
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredCategories.map((c) => {
            const IconComp = getCategoryIconComponent(c.slug || c.name_fr);
            const attrs = c.attributes || [];
            return (
              <div
                key={c.id}
                className="bg-white rounded-2xl border border-[#D4AF62]/40 shadow-sm hover:shadow-md transition-all flex flex-col justify-between overflow-hidden"
              >
                {/* Card Top */}
                <div className="p-5 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="p-3 rounded-2xl bg-[#063D2E] text-[#D4AF62] shadow-sm">
                        <IconComp className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="font-serif font-bold text-base text-[#063D2E] leading-tight">
                          {c.name_fr}
                        </h3>
                        <div className="flex items-center gap-2 mt-0.5">
                          {c.name_ar && (
                            <span className="text-xs text-gray-500 font-medium font-sans" dir="rtl">
                              {c.name_ar}
                            </span>
                          )}
                          <span className="text-[11px] font-mono text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                            #{c.slug}
                          </span>
                        </div>
                      </div>
                    </div>

                    <span className="text-[11px] font-mono text-gray-400 font-semibold">
                      Ordre #{c.display_order ?? 1}
                    </span>
                  </div>

                  {c.description_fr && (
                    <p className="text-xs text-gray-600 line-clamp-2 leading-relaxed">
                      {c.description_fr}
                    </p>
                  )}

                  {/* Status Pills */}
                  <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[11px]">
                    <span
                      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-bold ${
                        c.show_on_homepage
                          ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                          : "bg-gray-100 text-gray-500 border border-gray-200"
                      }`}
                    >
                      {c.show_on_homepage ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                      <span>{c.show_on_homepage ? "Accueil : Visible" : "Accueil : Masqué"}</span>
                    </span>

                    <span className="px-2.5 py-0.5 rounded-full bg-[#F8F6F0] text-[#063D2E] font-bold border border-[#D4AF62]/30">
                      {attrs.length} attribut(s)
                    </span>
                  </div>

                  {/* Dynamic Attributes List for this category */}
                  <div className="pt-2 border-t border-gray-100 space-y-1.5">
                    <div className="flex items-center justify-between text-[11px] font-bold text-gray-500">
                      <span>Attributs &amp; Filtres :</span>
                      <button
                        type="button"
                        onClick={() => setQuickAttrCategory(c)}
                        className="text-[#063D2E] hover:underline flex items-center gap-1"
                      >
                        <Plus className="w-3 h-3" />
                        <span>Ajouter</span>
                      </button>
                    </div>

                    {attrs.length === 0 ? (
                      <p className="text-[11px] text-gray-400 italic">Aucun attribut spécifique configuré.</p>
                    ) : (
                      <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                        {attrs.map((a: any) => (
                          <span
                            key={a.id}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-[#F8F6F0] border border-gray-200 text-[11px] text-gray-700 font-medium"
                          >
                            <strong>{a.label_fr}</strong>
                            <span className="text-[10px] text-gray-400 font-mono">
                              ({a.input_type}
                              {a.is_variant_axis ? " • Var." : ""})
                            </span>
                            <button
                              type="button"
                              onClick={() => handleDeleteAttribute(a.id)}
                              className="text-red-500 hover:text-red-800 font-bold ml-0.5"
                              title="Supprimer cet attribut"
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Card Action Buttons Toolbar */}
                <div className="p-3 bg-[#F8F6F0]/80 border-t border-gray-100 flex items-center justify-between gap-1 text-xs font-bold">
                  <button
                    type="button"
                    onClick={() => handleToggleCategoryHomepage(c)}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-white transition"
                    title={c.show_on_homepage ? "Masquer de la page d'accueil" : "Afficher sur la page d'accueil"}
                  >
                    {c.show_on_homepage ? <EyeOff className="w-3.5 h-3.5 text-gray-500" /> : <Eye className="w-3.5 h-3.5 text-emerald-600" />}
                    <span>{c.show_on_homepage ? "Masquer" : "Accueil"}</span>
                  </button>

                  <div className="flex items-center gap-1.5">
                    {/* EDIT CATEGORY BUTTON */}
                    <button
                      type="button"
                      onClick={() => handleOpenEdit(c)}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white border border-[#D4AF62] text-[#063D2E] hover:bg-[#D4AF62]/20 transition shadow-sm"
                      title="Modifier les noms, slug, description et icône"
                    >
                      <Edit3 className="w-3.5 h-3.5 text-[#063D2E]" />
                      <span>Modifier</span>
                    </button>

                    {/* DELETE / ARCHIVE BUTTON */}
                    <button
                      type="button"
                      onClick={() => setDeletingCategory(c)}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-red-50 border border-red-200 text-red-700 hover:bg-red-100 transition"
                      title="Archiver ou Supprimer définitivement cette catégorie"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-red-600" />
                      <span>Supprimer</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* EDIT CATEGORY MODAL */}
      {editingCategory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl border-2 border-[#D4AF62] shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto space-y-4 p-6">
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62]">
                  <Edit3 className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-lg font-serif font-bold text-[#063D2E]">
                    Modifier la Catégorie : {editingCategory.name_fr}
                  </h2>
                  <p className="text-xs text-gray-500">Mettez à jour les traductions, le slug et la visibilité.</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setEditingCategory(null)}
                className="text-gray-400 hover:text-gray-700"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmitEdit} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-bold mb-1 text-gray-700">Nom Français (FR) *</label>
                  <input
                    value={editNameFr}
                    onChange={(e) => setEditNameFr(e.target.value)}
                    required
                    className="w-full px-3 py-2 border rounded-xl font-bold"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1 text-gray-700">Nom Arabe (AR)</label>
                  <input
                    value={editNameAr}
                    onChange={(e) => setEditNameAr(e.target.value)}
                    dir="rtl"
                    className="w-full px-3 py-2 border rounded-xl"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1 text-gray-700">Nom Anglais (EN)</label>
                  <input
                    value={editNameEn}
                    onChange={(e) => setEditNameEn(e.target.value)}
                    className="w-full px-3 py-2 border rounded-xl"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold mb-1 text-gray-700">Slug URL *</label>
                  <input
                    value={editSlug}
                    onChange={(e) => setEditSlug(e.target.value)}
                    required
                    className="w-full px-3 py-2 border rounded-xl font-mono text-gray-700"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1 text-gray-700">Ordre d'affichage</label>
                  <input
                    type="number"
                    value={editOrder}
                    onChange={(e) => setEditOrder(Number(e.target.value))}
                    className="w-full px-3 py-2 border rounded-xl font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block font-bold mb-1 text-gray-700">Description (FR)</label>
                <textarea
                  value={editDescFr}
                  onChange={(e) => setEditDescFr(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 border rounded-xl"
                  placeholder="Description affichée sur la boutique..."
                />
              </div>

              {/* Icon Choice */}
              <div className="p-3 bg-[#F8F6F0] rounded-xl border border-gray-200 space-y-2">
                <label className="block font-bold text-[#063D2E]">Icône de représentation :</label>
                <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                  {LUXURY_ICONS.map((item) => {
                    const Icon = item.icon;
                    const isSelected = editIconKey === item.key;
                    return (
                      <button
                        key={item.key}
                        type="button"
                        onClick={() => setEditIconKey(item.key)}
                        className={`flex flex-col items-center gap-1.5 p-2.5 rounded-xl border transition ${
                          isSelected
                            ? "bg-[#063D2E] text-[#D4AF62] border-[#D4AF62] shadow-sm font-bold"
                            : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                        }`}
                      >
                        <Icon className="w-5 h-5" />
                        <span className="text-[10px] text-center truncate w-full">{item.label.split(" ")[0]}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Toggles */}
              <div className="flex flex-wrap gap-5 p-3 rounded-xl bg-gray-50 border border-gray-200">
                <label className="inline-flex items-center gap-2 cursor-pointer font-bold text-gray-800">
                  <input
                    type="checkbox"
                    checked={editShowHomepage}
                    onChange={(e) => setEditShowHomepage(e.target.checked)}
                    className="w-4 h-4 rounded text-[#063D2E]"
                  />
                  <span>Afficher sur la Page d'Accueil</span>
                </label>

                <label className="inline-flex items-center gap-2 cursor-pointer font-bold text-gray-800">
                  <input
                    type="checkbox"
                    checked={editIsActive}
                    onChange={(e) => setEditIsActive(e.target.checked)}
                    className="w-4 h-4 rounded text-[#063D2E]"
                  />
                  <span>Catégorie Active</span>
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t">
                <button
                  type="button"
                  onClick={() => setEditingCategory(null)}
                  className="px-4 py-2 rounded-xl border border-gray-300 font-bold text-gray-700"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={savingEdit}
                  className="px-6 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold shadow hover:bg-[#02291F] transition"
                >
                  {savingEdit ? "Enregistrement..." : "Enregistrer les modifications"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DELETE / ARCHIVE MODAL */}
      {deletingCategory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl border-2 border-red-300 shadow-2xl max-w-lg w-full space-y-4 p-6 text-xs">
            <div className="flex items-center gap-3 text-red-700">
              <div className="p-2.5 rounded-xl bg-red-100">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              <div>
                <h3 className="text-base font-serif font-bold">
                  Supprimer ou Archiver la Catégorie
                </h3>
                <p className="text-gray-500 font-medium">« {deletingCategory.name_fr} » (#{deletingCategory.slug})</p>
              </div>
            </div>

            <p className="text-gray-600 leading-relaxed">
              Choisissez l'action appropriée selon vos besoins de gestion du catalogue :
            </p>

            <div className="space-y-3">
              {/* Option 1: Safe Archive */}
              <div className="p-3.5 rounded-xl border border-amber-300 bg-amber-50 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-amber-900 flex items-center gap-1.5">
                    <Archive className="w-4 h-4 text-amber-700" />
                    <span>Option 1 : Archiver (Recommandé)</span>
                  </span>
                  <span className="px-2 py-0.5 rounded bg-amber-200 text-amber-900 font-bold text-[10px]">
                    Sans Risque
                  </span>
                </div>
                <p className="text-gray-600 text-[11px]">
                  Désactive immédiatement la catégorie sur la boutique sans affecter les produits déjà créés ni les commandes passées.
                </p>
                <button
                  type="button"
                  onClick={() => handleArchiveCategory(deletingCategory.id, deletingCategory.name_fr)}
                  className="w-full py-2 rounded-xl bg-amber-700 text-white font-extrabold hover:bg-amber-800 transition flex items-center justify-center gap-1.5"
                >
                  <Archive className="w-4 h-4 text-white" />
                  <span>Archiver la catégorie</span>
                </button>
              </div>

              {/* Option 2: Hard Delete */}
              <div className="p-3.5 rounded-xl border border-red-300 bg-red-50 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-red-900 flex items-center gap-1.5">
                    <Trash2 className="w-4 h-4 text-red-600" />
                    <span>Option 2 : Supprimer Définitivement</span>
                  </span>
                  <span className="px-2 py-0.5 rounded bg-red-200 text-red-900 font-bold text-[10px]">
                    Irréversible
                  </span>
                </div>
                <p className="text-gray-600 text-[11px]">
                  Supprime définitivement la catégorie et son schéma d'attributs de la base de données. Échouera si des produits y sont encore rattachés.
                </p>
                <button
                  type="button"
                  disabled={isDeleting}
                  onClick={() => handlePermanentDeleteCategory(deletingCategory.id, deletingCategory.name_fr)}
                  className="w-full py-2 rounded-xl bg-red-700 text-white font-extrabold hover:bg-red-800 transition disabled:opacity-50 flex items-center justify-center gap-1.5"
                >
                  <Trash2 className="w-4 h-4 text-white" />
                  <span>{isDeleting ? "Suppression en cours..." : "Supprimer Définitivement"}</span>
                </button>
              </div>
            </div>

            <div className="pt-2 text-right">
              <button
                type="button"
                onClick={() => setDeletingCategory(null)}
                className="px-4 py-2 rounded-xl border border-gray-300 font-bold text-gray-700"
              >
                Annuler
              </button>
            </div>
          </div>
        </div>
      )}

      {/* QUICK ADD ATTRIBUTE MODAL */}
      {quickAttrCategory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl border-2 border-[#D4AF62] shadow-2xl max-w-lg w-full space-y-4 p-6 text-xs">
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62]">
                  <Plus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-serif font-bold text-base text-[#063D2E]">
                    Ajouter un attribut à « {quickAttrCategory.name_fr} »
                  </h3>
                  <p className="text-gray-500 font-medium">Adapte le formulaire produit et les filtres boutique.</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setQuickAttrCategory(null)}
                className="text-gray-400 hover:text-gray-700"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddAttributeToExisting} className="space-y-3">
              <div>
                <label className="block font-bold mb-1 text-gray-700">Clé technique (minuscules sans espaces) *</label>
                <input
                  value={quickAttrKey}
                  onChange={(e) => setQuickAttrKey(e.target.value)}
                  placeholder="ex: pointure, matiere, calibre"
                  required
                  className="w-full px-3 py-2 border rounded-xl font-mono text-gray-800"
                />
              </div>

              <div>
                <label className="block font-bold mb-1 text-gray-700">Libellé en Français *</label>
                <input
                  value={quickAttrLabelFr}
                  onChange={(e) => setQuickAttrLabelFr(e.target.value)}
                  placeholder="ex: Pointure Chaussure"
                  required
                  className="w-full px-3 py-2 border rounded-xl font-bold"
                />
              </div>

              <div>
                <label className="block font-bold mb-1 text-gray-700">Type de données</label>
                <select
                  value={quickAttrType}
                  onChange={(e) => setQuickAttrType(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl bg-white"
                >
                  {ATTRIBUTE_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-bold mb-1 text-gray-700">Options prédéfinies (séparées par virgules)</label>
                <input
                  value={quickAttrOptions}
                  onChange={(e) => setQuickAttrOptions(e.target.value)}
                  placeholder="ex: 37, 38, 39, 40, 41"
                  className="w-full px-3 py-2 border rounded-xl"
                />
              </div>

              <div className="flex flex-col gap-2 pt-1 p-3 rounded-xl bg-[#F8F6F0] border">
                <label className="inline-flex items-center gap-2 cursor-pointer font-bold text-gray-800">
                  <input
                    type="checkbox"
                    checked={quickAttrVariant}
                    onChange={(e) => setQuickAttrVariant(e.target.checked)}
                  />
                  <span>Axe de variante (génère stocks et prix distincts)</span>
                </label>
                <label className="inline-flex items-center gap-2 cursor-pointer font-bold text-gray-800">
                  <input
                    type="checkbox"
                    checked={quickAttrFilterable}
                    onChange={(e) => setQuickAttrFilterable(e.target.checked)}
                  />
                  <span>Afficher dans les filtres de recherche</span>
                </label>
                <label className="inline-flex items-center gap-2 cursor-pointer font-bold text-gray-800">
                  <input
                    type="checkbox"
                    checked={quickAttrRequired}
                    onChange={(e) => setQuickAttrRequired(e.target.checked)}
                  />
                  <span>Champ obligatoire lors de la création d'article</span>
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t">
                <button
                  type="button"
                  onClick={() => setQuickAttrCategory(null)}
                  className="px-4 py-2 rounded-xl border border-gray-300 font-bold text-gray-700"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={savingQuickAttr}
                  className="px-6 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold shadow hover:bg-[#02291F] transition"
                >
                  {savingQuickAttr ? "Ajout en cours..." : "+ Ajouter l'attribut"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
