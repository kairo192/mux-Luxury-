import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronRight,
  Image as ImageIcon,
  Layers,
  Loader2,
  RefreshCw,
  Save,
  Search,
  Sparkles,
  Star,
  Tag,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { notifyClientError, notifyClientSuccess, notifyClientWarning } from "../utils/clientNotifier";
import { VariantManager, EditorVariant, VariantAxis } from "./VariantManager";
import { LiveProductCardPreview } from "./LiveProductCardPreview";
import { useT } from "../i18n";

// ============================================================================
// FULL DYNAMIC PRODUCT EDITOR (create + edit)
// Every field is persisted through the existing FastAPI product endpoints,
// variants go through the real variant CRUD endpoints, and image uploads use
// the verified /admin/upload endpoint. No mock data anywhere.
// ============================================================================

type Props = {
  open: boolean;
  product: any | null;
  categories: any[];
  brands: any[];
  onClose: () => void;
  onSaved: () => Promise<void> | void;
  initialCategoryId?: number;
};

type Draft = {
  id?: number;
  version?: number;
  category_id: number | "";
  brand_id: number | "";
  name_fr: string;
  name_ar: string;
  name_en: string;
  description_fr: string;
  description_ar: string;
  description_en: string;
  slug: string;
  sku: string;
  barcode: string;
  purchase_cost_dzd: number;
  selling_price_dzd: number;
  previous_price_dzd: number | "";
  discount_percent: number;
  status: "draft" | "published" | "archived";
  is_featured: boolean;
  is_new_arrival: boolean;
  main_image_url: string;
  seo_title: string;
  seo_description: string;
  weight_grams: number | "";
  dimensions_cm: string;
  tags: string;
  dynamic_attributes: Record<string, string>;
  variants: EditorVariant[];
};

const EMPTY: Draft = {
  category_id: "",
  brand_id: "",
  name_fr: "",
  name_ar: "",
  name_en: "",
  description_fr: "",
  description_ar: "",
  description_en: "",
  slug: "",
  sku: "",
  barcode: "",
  purchase_cost_dzd: 0,
  selling_price_dzd: 0,
  previous_price_dzd: "",
  discount_percent: 0,
  status: "draft",
  is_featured: false,
  is_new_arrival: false,
  main_image_url: "",
  seo_title: "",
  seo_description: "",
  weight_grams: "",
  dimensions_cm: "",
  tags: "",
  dynamic_attributes: {},
  variants: [],
};

function slugify(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 160);
}

function draftFromProduct(product: any): Draft {
  return {
    ...EMPTY,
    id: product.id,
    version: product.version,
    category_id: product.category_id ?? "",
    brand_id: product.brand_id ?? "",
    name_fr: product.name_fr || "",
    name_ar: product.name_ar || "",
    name_en: product.name_en || "",
    description_fr: product.description_fr || "",
    description_ar: product.description_ar || "",
    description_en: product.description_en || "",
    slug: product.slug || "",
    sku: product.sku || "",
    barcode: product.barcode || "",
    purchase_cost_dzd: Number(product.purchase_cost_dzd ?? 0),
    selling_price_dzd: Number(product.selling_price_dzd ?? 0),
    previous_price_dzd: product.previous_price_dzd ?? "",
    discount_percent: Number(product.discount_percent ?? 0),
    status: product.status || "draft",
    is_featured: Boolean(product.is_featured),
    is_new_arrival: Boolean(product.is_new_arrival),
    main_image_url: product.main_image_url || "",
    seo_title: product.seo_title || "",
    seo_description: product.seo_description || "",
    weight_grams: product.weight_grams ?? "",
    dimensions_cm: product.dimensions_cm || "",
    tags: product.tags || "",
    dynamic_attributes: { ...(product.attributes || {}) },
    variants: (product.variants || []).map((v: any) => ({
      id: v.id,
      sku: v.sku,
      title: v.title,
      stock_qty: Number(v.stock_qty || 0),
      price_override_dzd: v.price_override_dzd,
      barcode: v.barcode || "",
      low_stock_threshold: Number(v.low_stock_threshold ?? 3),
      is_active: v.is_active !== false,
      effective_price_dzd: v.effective_price_dzd,
      attributes: { ...(v.attributes || {}) },
    })),
  };
}

function labelForType(inputType?: string) {
  switch (inputType) {
    case "long_text":
      return "Description longue";
    case "number":
    case "price":
      return "Numérique";
    case "measurement":
      return "Mesure";
    case "boolean":
      return "Oui / Non";
    case "date":
      return "Date";
    default:
      return "Texte";
  }
}

export function ProductEditor({ open, product, categories, brands, onClose, onSaved, initialCategoryId }: Props) {
  const t = useT();
  const isCreate = !product;
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [initialSnapshot, setInitialSnapshot] = useState("");
  const [tab, setTab] = useState<"general" | "variants" | "images" | "seo">("general");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [slugTouched, setSlugTouched] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const [conflict, setConflict] = useState("");
  const [pendingImages, setPendingImages] = useState<string[]>([]);
  const [galleryBusy, setGalleryBusy] = useState<number | null>(null);
  const [categorySearch, setCategorySearch] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const galleryInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadTarget, setUploadTarget] = useState<"main" | "gallery">("main");
  const [localBrands, setLocalBrands] = useState<any[]>(brands);
  const [showNewBrandForm, setShowNewBrandForm] = useState(false);
  const [newBrandName, setNewBrandName] = useState("");
  const [newBrandLogoUrl, setNewBrandLogoUrl] = useState("");
  const [creatingBrand, setCreatingBrand] = useState(false);
  const [showLivePreview, setShowLivePreview] = useState(true);

  useEffect(() => {
    setLocalBrands(brands);
  }, [brands]);

  async function handleCreateBrand() {
    if (!newBrandName.trim()) return;
    setCreatingBrand(true);
    try {
      const slug = slugify(newBrandName);
      const created = await DesktopCmsApi.createBrand({
        name: newBrandName.trim(),
        slug,
        logo_url: newBrandLogoUrl.trim() || undefined,
      });
      setLocalBrands((prev) => [...prev, created]);
      patch({ brand_id: created.id });
      setShowNewBrandForm(false);
      setNewBrandName("");
      setNewBrandLogoUrl("");
      notifyClientSuccess("Marque créée", `La marque « ${created.name} » a été enregistrée.`);
    } catch (err: any) {
      notifyClientError("Échec création marque", err.message || "Erreur réseau.");
    } finally {
      setCreatingBrand(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    const next = product ? draftFromProduct(product) : { ...EMPTY, category_id: initialCategoryId ?? (categories[0]?.id ?? "") };
    setDraft(next);
    setInitialSnapshot(JSON.stringify(next));
    setTab("general");
    setConfirmClose(false);
    setConflict("");
    setPendingImages([]);
    setSlugTouched(Boolean(product));
    setCategorySearch("");
  }, [open, product?.id]);

  const category = useMemo(
    () => categories.find((c) => c.id === Number(draft.category_id)),
    [categories, draft.category_id]
  );

  const axes: VariantAxis[] = useMemo(
    () => (category?.attributes || []).filter((a: any) => a.is_variant_axis),
    [category]
  );
  const dataAttributes = useMemo(
    () => (category?.attributes || []).filter((a: any) => !a.is_variant_axis),
    [category]
  );

  const dirty = JSON.stringify(draft) !== initialSnapshot;

  function patch(partial: Partial<Draft>) {
    setDraft((prev) => ({ ...prev, ...partial }));
  }

  function handleNameChange(value: string) {
    setDraft((prev) => ({
      ...prev,
      name_fr: value,
      slug: slugTouched ? prev.slug : slugify(value),
    }));
  }

  function handlePriceChange(field: "selling_price_dzd" | "previous_price_dzd", raw: string) {
    setDraft((prev) => {
      const next: Draft = { ...prev, [field]: raw === "" ? "" : Math.max(0, Number(raw)) };
      const sell = Number(field === "selling_price_dzd" ? next.selling_price_dzd : next.selling_price_dzd) || 0;
      const prevPrice = Number(next.previous_price_dzd) || 0;
      if (sell > 0 && prevPrice > sell) {
        next.discount_percent = Math.round(((prevPrice - sell) / prevPrice) * 100);
      } else if (field === "previous_price_dzd" && raw === "") {
        next.discount_percent = 0;
      }
      return next;
    });
  }

  async function handleUpload(file: File, target: "main" | "gallery") {
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      notifyClientWarning("Format non supporté", "Formats acceptés : JPEG, PNG ou WEBP.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      notifyClientWarning("Image trop volumineuse", "La taille maximale est de 5 Mo.");
      return;
    }
    setUploading(true);
    try {
      const uploaded = await DesktopCmsApi.uploadMediaFile(file);
      if (target === "main") {
        patch({ main_image_url: uploaded.url });
        notifyClientSuccess("Image principale prête", `Fichier vérifié : ${uploaded.url}`);
      } else if (isCreate) {
        setPendingImages((prev) => [...prev, uploaded.url]);
        notifyClientSuccess("Image ajoutée au brouillon", `${uploaded.url} sera enregistrée avec le produit.`);
      } else {
        await addGalleryImage(uploaded.url);
      }
    } catch (err: any) {
      notifyClientError(err, "Téléversement de l'image refusé");
    } finally {
      setUploading(false);
    }
  }

  async function addGalleryImage(url: string) {
    if (!draft.id) {
      setPendingImages((prev) => (prev.includes(url) ? prev : [...prev, url]));
      return;
    }
    if (!url.trim()) {
      notifyClientWarning("URL requise", "Téléversez une image ou saisissez son chemin.");
      return;
    }
    setGalleryBusy(-1);
    try {
      const img = await DesktopCmsApi.addProductImage(draft.id, {
        image_url: url.trim(),
        alt_text: draft.name_fr || "Mus Luxury",
        display_order: (product?.gallery_images?.length || 0) + 1,
      });
      await DesktopCmsApi.reorderProductImages(draft.id, {
        orders: [{ image_id: img.id, display_order: (product?.gallery_images?.length || 0) + 1 }],
      });
      notifyClientSuccess("Galerie mise à jour", "Nouvelle image ajoutée au produit.");
      await onSaved();
    } catch (err: any) {
      notifyClientError(err, "Ajout de l'image impossible");
    } finally {
      setGalleryBusy(null);
    }
  }

  async function removeGalleryImage(imageId: number) {
    setGalleryBusy(imageId);
    try {
      await DesktopCmsApi.deleteProductImage(imageId);
      notifyClientSuccess("Image retirée", "L'image a été supprimée de la galerie.");
      await onSaved();
    } catch (err: any) {
      notifyClientError(err, "Suppression de l'image impossible");
    } finally {
      setGalleryBusy(null);
    }
  }

  async function setPrimaryImage(url: string) {
    if (!draft.id) {
      patch({ main_image_url: url });
      return;
    }
    setGalleryBusy(-2);
    try {
      const images = product?.gallery_images || [];
      await DesktopCmsApi.reorderProductImages(draft.id, {
        orders: images.map((img: any, idx: number) => ({
          image_id: img.id,
          display_order: img.image_url === url ? 1 : idx + 2,
        })),
        primary_image_url: url,
      });
      notifyClientSuccess("Image principale définie", "La vitrine utilisera cette image en premier.");
      await onSaved();
    } catch (err: any) {
      notifyClientError(err, "Choix de l'image principale impossible");
    } finally {
      setGalleryBusy(null);
    }
  }

  function validate(): string | null {
    if (!draft.category_id) return "Sélectionnez une catégorie.";
    if (!draft.name_fr.trim()) return "Le nom du produit (français) est obligatoire.";
    if (!draft.sku.trim()) return "La référence SKU est obligatoire.";
    if (!/^[a-z0-9-]{2,160}$/.test(draft.slug)) return "Le slug doit contenir 2 à 160 caractères (a-z, 0-9 et tirets).";
    if (Number(draft.selling_price_dzd) <= 0) return "Le prix de vente doit être strictement supérieur à 0.";
    if (Number(draft.purchase_cost_dzd) < 0) return "Le coût d'achat ne peut pas être négatif.";
    if (draft.previous_price_dzd !== "" && Number(draft.previous_price_dzd) < Number(draft.selling_price_dzd)) {
      return "Le prix barré doit être supérieur au prix de vente.";
    }
    if (Number(draft.selling_price_dzd) < Number(draft.purchase_cost_dzd)) {
      return "Le prix de vente est inférieur au coût d'achat : la marge serait négative.";
    }
    if (draft.status === "published") {
      const missing = dataAttributes.filter(
        (a: any) => a.is_required && !String(draft.dynamic_attributes[a.attr_key] || "").trim()
      );
      if (missing.length) return `Caractéristiques obligatoires manquantes : ${missing.map((a: any) => a.label_fr).join(", ")}.`;
      if (!draft.main_image_url.trim()) return "Ajoutez une image principale avant de publier le produit.";
      if (!draft.variants.length) return "Ajoutez au moins une déclinaison avant de publier le produit.";
    }
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    e.stopPropagation();
    setConflict("");
    const problem = validate();
    if (problem) {
      notifyClientWarning("Fiche produit incomplète", problem);
      return;
    }
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        category_id: Number(draft.category_id),
        brand_id: draft.brand_id === "" ? null : Number(draft.brand_id),
        name_fr: draft.name_fr.trim(),
        name_ar: draft.name_ar.trim(),
        name_en: draft.name_en.trim(),
        description_fr: draft.description_fr,
        description_ar: draft.description_ar,
        description_en: draft.description_en,
        slug: draft.slug.trim(),
        sku: draft.sku.trim(),
        barcode: draft.barcode.trim(),
        purchase_cost_dzd: Number(draft.purchase_cost_dzd) || 0,
        selling_price_dzd: Number(draft.selling_price_dzd),
        previous_price_dzd: draft.previous_price_dzd === "" ? null : Number(draft.previous_price_dzd),
        discount_percent: Number(draft.discount_percent) || 0,
        status: draft.status,
        is_featured: draft.is_featured,
        is_new_arrival: draft.is_new_arrival,
        main_image_url: draft.main_image_url.trim() || null,
        seo_title: draft.seo_title.trim() || null,
        seo_description: draft.seo_description.trim() || null,
        weight_grams: draft.weight_grams === "" ? null : Number(draft.weight_grams),
        dimensions_cm: draft.dimensions_cm.trim() || null,
        tags: draft.tags.trim() || null,
        dynamic_attributes: draft.dynamic_attributes,
      };

      if (isCreate) {
        payload.variants = draft.variants.map((v) => ({
          sku: v.sku,
          title: v.title,
          barcode: v.barcode || null,
          price_override_dzd: v.price_override_dzd === null || v.price_override_dzd === undefined ? null : Number(v.price_override_dzd),
          stock_qty: Number(v.stock_qty) || 0,
          low_stock_threshold: Number(v.low_stock_threshold ?? 3),
          attributes: v.attributes,
        }));
        const created = await DesktopCmsApi.createProduct(payload);
        const newId = created?.id;
        if (newId) {
          for (const url of pendingImages) {
            try {
              await DesktopCmsApi.addProductImage(newId, { image_url: url, alt_text: draft.name_fr, display_order: 1 });
            } catch {
              /* gallery image failures must not roll back a created product */
            }
          }
        }
        notifyClientSuccess(
          "Produit créé",
          `« ${draft.name_fr} » et ses ${draft.variants.length} déclinaison(s) sont en ligne.`
        );
      } else {
        payload.expected_version = Number(draft.version || 1);
        await DesktopCmsApi.updateProduct(draft.id!, payload);
        notifyClientSuccess("Fiche produit enregistrée", `« ${draft.name_fr} » a été mise à jour sur la boutique.`);
      }
      await onSaved();
      setInitialSnapshot(JSON.stringify(draft));
      onClose();
    } catch (err: any) {
      const status = err?.status;
      if (status === 409) {
        setConflict(err?.userMessage || "Un autre poste a modifié ce produit entre-temps.");
      } else {
        setConflict("");
        notifyClientError(err, isCreate ? "Création du produit impossible" : "Enregistrement du produit impossible");
      }
    } finally {
      setSaving(false);
    }
  }

  function requestClose() {
    if (dirty && !saving) {
      setConfirmClose(true);
      return;
    }
    onClose();
  }

  async function reloadLatest() {
    const res = await DesktopCmsApi.listAdminProducts({ include_archived: true });
    const latest = (res?.items || []).find((p: any) => p.id === draft.id);
    if (latest) {
      const fresh = draftFromProduct(latest);
      setDraft(fresh);
      setInitialSnapshot(JSON.stringify(fresh));
      setConflict("");
      notifyClientSuccess("Données rechargées", `Version serveur v${latest.version} chargée.`);
      await onSaved();
    }
  }

  if (!open) return null;

  const margin = Number(draft.selling_price_dzd) - Number(draft.purchase_cost_dzd);
  const marginPct = Number(draft.selling_price_dzd) > 0 ? (margin / Number(draft.selling_price_dzd)) * 100 : 0;
  const gallery = (product?.gallery_images || []) as any[];
  const filteredCategories = categories.filter(
    (c) => !categorySearch || `${c.name_fr} ${c.name_en || ""}`.toLowerCase().includes(categorySearch.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-start justify-center overflow-y-auto p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-7xl bg-white rounded-3xl shadow-2xl border border-[#D4AF62]/50 my-6 overflow-hidden text-xs"
      >
        {/* Header */}
        <div className="px-6 py-4 bg-gradient-to-r from-[#063D2E] to-[#0A5C45] text-white flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/10 border border-[#D4AF62]/40 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-[#D4AF62]" />
            </div>
            <div>
              <h3 className="font-serif font-bold text-lg text-[#E8D4A5]">
                {isCreate ? t("product_editor.title_create") : t("product_editor.title_edit", { name: draft.name_fr || "produit" })}
              </h3>
              <p className="text-[11px] text-white/70">
                {isCreate
                  ? t("product_editor.subtitle_create")
                  : t("product_editor.subtitle_edit", { sku: draft.sku, version: draft.version || 1 })}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowLivePreview(!showLivePreview)}
              className={`hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-bold text-xs transition border ${
                showLivePreview
                  ? "bg-[#D4AF62] text-[#02291F] border-[#D4AF62]"
                  : "bg-white/10 text-white/90 border-white/20 hover:bg-white/20"
              }`}
            >
              <span>{showLivePreview ? t("product_editor.btn_preview_active") : t("product_editor.btn_preview_show")}</span>
            </button>
            <button
              type="button"
              onClick={requestClose}
              className="p-2 rounded-xl bg-white/10 hover:bg-white/20 transition"
              title={t("common.close")}
            >
              <X className="w-4 h-4 text-[#E8D4A5]" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 px-6 pt-3 bg-[#F8F6F0] border-b border-[#D4AF62]/30 overflow-x-auto">
          {[
            { key: "general", label: t("product_editor.tab_info"), icon: Tag },
            { key: "variants", label: t("product_editor.tab_variants", { count: draft.variants.length }), icon: Layers },
            { key: "images", label: t("product_editor.tab_images", { count: gallery.length + pendingImages.length }), icon: ImageIcon },
            { key: "seo", label: t("product_editor.tab_seo"), icon: Search },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setTab(item.key as any)}
                className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-t-xl font-bold whitespace-nowrap transition ${
                  tab === item.key
                    ? "bg-white text-[#063D2E] border border-[#D4AF62]/40 border-b-white -mb-px"
                    : "text-gray-500 hover:text-[#063D2E]"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        {/* Body */}
        <div className="p-6 max-h-[72vh] overflow-y-auto">
          <div className={`grid grid-cols-1 ${showLivePreview ? "lg:grid-cols-12" : ""} gap-6 items-start`}>
            <div className={`${showLivePreview ? "lg:col-span-8" : "w-full"} space-y-5`}>
          {conflict && (
            <div className="p-3 rounded-xl bg-amber-50 border border-amber-300 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-bold text-amber-900">{t("product_editor.conflict_title")}</p>
                <p className="text-amber-800 text-[11px] mt-0.5">{conflict}</p>
              </div>
              <button
                type="button"
                onClick={reloadLatest}
                className="px-2.5 py-1 rounded-lg bg-amber-700 text-white font-bold flex items-center gap-1 shrink-0"
              >
                <RefreshCw className="w-3 h-3" /> {t("product_editor.btn_reload")}
              </button>
            </div>
          )}

          {confirmClose && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0" />
              <p className="flex-1 text-rose-900 font-semibold">
                {t("product_editor.unsaved_warning")}
              </p>
              <button type="button" onClick={() => setConfirmClose(false)} className="px-2.5 py-1 rounded-lg bg-white border border-rose-300 font-bold text-rose-800">
                {t("product_editor.btn_continue_editing")}
              </button>
              <button type="button" onClick={onClose} className="px-2.5 py-1 rounded-lg bg-rose-700 text-white font-bold">
                {t("product_editor.btn_discard_close")}
              </button>
            </div>
          )}

          {/* ---------------- GENERAL ---------------- */}
          {tab === "general" && (
            <div className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="md:col-span-2">
                  <label className="block font-bold mb-1">{t("product_editor.category_label")}</label>
                  <div className="flex items-center gap-2">
                    <input
                      value={categorySearch}
                      onChange={(e) => setCategorySearch(e.target.value)}
                      placeholder={t("product_editor.category_filter")}
                      className="w-40 px-2 py-1.5 border rounded-lg bg-[#F8F6F0]"
                    />
                    <select
                      value={draft.category_id}
                      onChange={(e) => patch({ category_id: e.target.value === "" ? "" : Number(e.target.value), dynamic_attributes: {} })}
                      className="flex-1 px-3 py-2 border rounded-xl bg-white font-semibold focus:border-[#063D2E] outline-none"
                    >
                      <option value="">{t("product_editor.category_placeholder")}</option>
                      {filteredCategories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name_fr} {c.deleted_at ? t("product_editor.category_archived") : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                  {category && (
                    <p className="text-[11px] text-gray-500 mt-1">
                      {t("product_editor.category_meta", { dataCount: dataAttributes.length, axesCount: axes.length })}
                      {axes.length > 0 ? ` (${axes.map((a: any) => a.label_fr).join(", ")})` : ""}
                    </p>
                  )}
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="font-bold">{t("product_editor.brand_label")}</label>
                    <button
                      type="button"
                      onClick={() => setShowNewBrandForm(!showNewBrandForm)}
                      className="text-[11px] font-bold text-[#063D2E] hover:underline"
                    >
                      {showNewBrandForm ? t("common.cancel") : t("product_editor.btn_new_brand")}
                    </button>
                  </div>
                  {showNewBrandForm ? (
                    <div className="p-3 rounded-xl bg-amber-500/10 border border-[#D4AF62]/40 space-y-2">
                      <input
                        value={newBrandName}
                        onChange={(e) => setNewBrandName(e.target.value)}
                        placeholder={t("product_editor.new_brand_name_placeholder")}
                        className="w-full px-3 py-1.5 border rounded-lg bg-white"
                      />
                      <div className="flex items-center gap-2">
                        <input
                          value={newBrandLogoUrl}
                          onChange={(e) => setNewBrandLogoUrl(e.target.value)}
                          placeholder={t("product_editor.new_brand_logo_placeholder")}
                          className="flex-1 px-3 py-1.5 border rounded-lg bg-white font-mono text-[11px]"
                        />
                        <button
                          type="button"
                          disabled={creatingBrand || !newBrandName.trim()}
                          onClick={handleCreateBrand}
                          className="px-3 py-1.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold disabled:opacity-50"
                        >
                          {creatingBrand ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : t("product_editor.btn_create_brand")}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <select
                      value={draft.brand_id}
                      onChange={(e) => patch({ brand_id: e.target.value === "" ? "" : Number(e.target.value) })}
                      className="w-full px-3 py-2 border rounded-xl bg-white"
                    >
                      <option value="">{t("product_editor.brand_placeholder")}</option>
                      {localBrands.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.name_fr_label")}</label>
                  <input
                    value={draft.name_fr}
                    onChange={(e) => handleNameChange(e.target.value)}
                    placeholder="ex: Sac Émeraude Prestige"
                    className="w-full px-3 py-2 border rounded-xl bg-white focus:border-[#063D2E] outline-none"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.name_ar_label")}</label>
                  <input
                    dir="rtl"
                    value={draft.name_ar}
                    onChange={(e) => patch({ name_ar: e.target.value })}
                    className="w-full px-3 py-2 border rounded-xl bg-white"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.name_en_label")}</label>
                  <input
                    value={draft.name_en}
                    onChange={(e) => patch({ name_en: e.target.value })}
                    className="w-full px-3 py-2 border rounded-xl bg-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.desc_fr_label")}</label>
                  <textarea
                    rows={4}
                    value={draft.description_fr}
                    onChange={(e) => patch({ description_fr: e.target.value })}
                    className="w-full px-3 py-2 border rounded-xl bg-white resize-y"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.desc_ar_label")}</label>
                  <textarea
                    dir="rtl"
                    rows={4}
                    value={draft.description_ar}
                    onChange={(e) => patch({ description_ar: e.target.value })}
                    className="w-full px-3 py-2 border rounded-xl bg-white resize-y"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.desc_en_label")}</label>
                  <textarea
                    rows={4}
                    value={draft.description_en}
                    onChange={(e) => patch({ description_en: e.target.value })}
                    className="w-full px-3 py-2 border rounded-xl bg-white resize-y"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.sku_label")}</label>
                  <input
                    value={draft.sku}
                    onChange={(e) => patch({ sku: e.target.value })}
                    placeholder="LUX-BAG-001"
                    className="w-full px-3 py-2 border rounded-xl font-mono uppercase bg-white"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.barcode_label")}</label>
                  <input
                    value={draft.barcode}
                    onChange={(e) => patch({ barcode: e.target.value })}
                    className="w-full px-3 py-2 border rounded-xl font-mono bg-white"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block font-bold mb-1">{t("product_editor.slug_label")}</label>
                  <input
                    value={draft.slug}
                    onChange={(e) => {
                      setSlugTouched(true);
                      patch({ slug: slugify(e.target.value) });
                    }}
                    className="w-full px-3 py-2 border rounded-xl font-mono bg-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 p-3 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30">
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.cost_label")}</label>
                  <input
                    type="number"
                    min={0}
                    value={draft.purchase_cost_dzd}
                    onChange={(e) => patch({ purchase_cost_dzd: Math.max(0, Number(e.target.value)) })}
                    className="w-full px-3 py-2 border rounded-xl font-mono bg-white"
                  />
                  <p className="text-[10px] text-gray-500 mt-1">{t("product_editor.cost_hint")}</p>
                </div>
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.price_label")}</label>
                  <input
                    type="number"
                    min={0}
                    value={draft.selling_price_dzd}
                    onChange={(e) => handlePriceChange("selling_price_dzd", e.target.value)}
                    className="w-full px-3 py-2 border rounded-xl font-bold font-mono text-[#063D2E] bg-white"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.prev_price_label")}</label>
                  <input
                    type="number"
                    min={0}
                    value={draft.previous_price_dzd}
                    onChange={(e) => handlePriceChange("previous_price_dzd", e.target.value)}
                    placeholder="Optionnel"
                    className="w-full px-3 py-2 border rounded-xl font-mono bg-white"
                  />
                  <p className="text-[10px] text-gray-500 mt-1">{t("product_editor.prev_price_hint")}</p>
                </div>
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.discount_label")}</label>
                  <input
                    type="number"
                    min={0}
                    max={95}
                    value={draft.discount_percent}
                    onChange={(e) => patch({ discount_percent: Math.min(95, Math.max(0, Number(e.target.value))) })}
                    className="w-full px-3 py-2 border rounded-xl font-mono bg-white"
                  />
                  <p className="text-[10px] text-gray-500 mt-1">{t("product_editor.discount_hint")}</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-4 p-3 rounded-xl border border-emerald-200 bg-emerald-50/60">
                <span className="font-bold text-[#063D2E]">{t("product_editor.unit_margin")}</span>
                <span className={`font-mono font-bold ${margin >= 0 ? "text-emerald-700" : "text-rose-700"}`}>
                  {margin >= 0 ? "+" : ""}
                  {margin.toLocaleString()} DA
                </span>
                <span className="px-2 py-0.5 rounded-full bg-white border border-emerald-200 font-mono font-bold">
                  {marginPct.toFixed(1)}%
                </span>
                <span className="text-gray-500 font-mono">
                  x{Number(draft.purchase_cost_dzd) > 0 ? (Number(draft.selling_price_dzd) / Number(draft.purchase_cost_dzd)).toFixed(2) : "—"}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block font-bold mb-1">{t("product_editor.status_label")}</label>
                  <select
                    value={draft.status}
                    onChange={(e) => patch({ status: e.target.value as Draft["status"] })}
                    className="w-full px-3 py-2 border rounded-xl bg-white font-bold"
                  >
                    <option value="draft">{t("product_editor.status_draft")}</option>
                    <option value="published">{t("product_editor.status_published")}</option>
                    <option value="archived">{t("product_editor.status_archived")}</option>
                  </select>
                </div>
                <div className="flex items-end gap-3">
                  <label className="flex items-center gap-2 px-3 py-2 rounded-xl border bg-white cursor-pointer">
                    <input
                      type="checkbox"
                      checked={draft.is_featured}
                      onChange={(e) => patch({ is_featured: e.target.checked })}
                      className="w-4 h-4"
                    />
                    <span className="font-bold flex items-center gap-1">
                      <Star className="w-3.5 h-3.5 text-[#D4AF62]" /> {t("product_editor.featured_label")}
                    </span>
                  </label>
                  <label className="flex items-center gap-2 px-3 py-2 rounded-xl border bg-white cursor-pointer">
                    <input
                      type="checkbox"
                      checked={draft.is_new_arrival}
                      onChange={(e) => patch({ is_new_arrival: e.target.checked })}
                      className="w-4 h-4"
                    />
                    <span className="font-bold">{t("product_editor.new_arrival_label")}</span>
                  </label>
                </div>
              </div>

              {dataAttributes.length > 0 && (
                <div className="p-4 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30 space-y-2">
                  <p className="font-bold text-[#063D2E]">
                    {t("product_editor.specs_title", { category: category?.name_fr || "", count: dataAttributes.length })}
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {dataAttributes.map((attr: any) => {
                      const hasOptions = (attr.options || []).length > 0;
                      const value = draft.dynamic_attributes[attr.attr_key] || "";
                      const setValue = (v: string) =>
                        patch({ dynamic_attributes: { ...draft.dynamic_attributes, [attr.attr_key]: v } });
                      return (
                        <div key={attr.attr_key}>
                          <label className="block font-semibold mb-1">
                            {attr.label_fr}
                            {attr.unit ? <span className="text-gray-400"> ({attr.unit})</span> : null}
                            {attr.is_required ? <span className="text-rose-600"> *</span> : null}
                            <span className="ml-1 text-[10px] text-gray-400 font-normal">
                              {labelForType(attr.input_type)}
                            </span>
                          </label>
                          {hasOptions ? (
                            <select
                              value={value}
                              onChange={(e) => setValue(e.target.value)}
                              className="w-full px-3 py-1.5 border rounded-lg bg-white"
                            >
                              <option value="">{t("product_editor.select_option")}</option>
                              {attr.options.map((o: any) => (
                                <option key={o.value} value={o.value}>
                                  {o.label_fr || o.value}
                                </option>
                              ))}
                            </select>
                          ) : attr.input_type === "long_text" ? (
                            <textarea
                              rows={2}
                              value={value}
                              onChange={(e) => setValue(e.target.value)}
                              className="w-full px-3 py-1.5 border rounded-lg bg-white"
                            />
                          ) : attr.input_type === "boolean" ? (
                            <select value={value} onChange={(e) => setValue(e.target.value)} className="w-full px-3 py-1.5 border rounded-lg bg-white">
                              <option value="">—</option>
                              <option value="Oui">Oui</option>
                              <option value="Non">Non</option>
                            </select>
                          ) : (
                            <input
                              type={["number", "price", "measurement"].includes(attr.input_type) ? "number" : attr.input_type === "date" ? "date" : "text"}
                              value={value}
                              onChange={(e) => setValue(e.target.value)}
                              className="w-full px-3 py-1.5 border rounded-lg bg-white"
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ---------------- VARIANTS ---------------- */}
          {tab === "variants" && (
            <VariantManager
              productId={draft.id ?? null}
              productSku={draft.sku}
              productPrice={Number(draft.selling_price_dzd) || 0}
              axes={axes}
              variants={draft.variants}
              onChange={(next) => patch({ variants: next })}
              onRefresh={onSaved}
            />
          )}

          {/* ---------------- IMAGES ---------------- */}
          {tab === "images" && (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl border border-[#D4AF62]/40 bg-[#F8F6F0] space-y-3">
                <p className="font-bold text-[#063D2E] flex items-center gap-2">
                  <ImageIcon className="w-4 h-4" /> {t("product_editor.main_image_title")}
                </p>
                <div className="flex flex-col md:flex-row gap-4">
                  <div className="w-40 h-40 rounded-xl bg-white border border-gray-200 flex items-center justify-center overflow-hidden shrink-0">
                    {draft.main_image_url ? (
                      <img src={draft.main_image_url} alt="Aperçu" className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-gray-400 text-[11px] px-3 text-center">{t("product_editor.no_image_selected")}</span>
                    )}
                  </div>
                  <div className="flex-1 space-y-2">
                    <input
                      value={draft.main_image_url}
                      onChange={(e) => patch({ main_image_url: e.target.value })}
                      placeholder="/assets/produit.jpg ou https://…"
                      className="w-full px-3 py-2 border rounded-xl bg-white font-mono"
                    />
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setUploadTarget("main");
                          fileInputRef.current?.click();
                        }}
                        disabled={uploading}
                        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold disabled:opacity-50"
                      >
                        {uploading && uploadTarget === "main" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <UploadCloud className="w-3.5 h-3.5" />}
                        <span>{t("product_editor.upload_from_computer")}</span>
                      </button>
                      {draft.main_image_url && (
                        <button
                          type="button"
                          onClick={() => patch({ main_image_url: "" })}
                          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white border border-rose-300 text-rose-700 font-bold"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> {t("product_editor.remove_image")}
                        </button>
                      )}
                    </div>
                    <p className="text-[11px] text-gray-500">
                      {t("product_editor.image_guidelines")}
                    </p>
                  </div>
                </div>
              </div>

              <div className="p-4 rounded-2xl border border-[#D4AF62]/40 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-bold text-[#063D2E]">{t("product_editor.gallery_title", { count: gallery.length + pendingImages.length })}</p>
                  <button
                    type="button"
                    onClick={() => {
                      setUploadTarget("gallery");
                      galleryInputRef.current?.click();
                    }}
                    disabled={uploading}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-[#063D2E] text-[#063D2E] font-bold disabled:opacity-50"
                  >
                    <UploadCloud className="w-3.5 h-3.5" /> {t("product_editor.btn_add_image")}
                  </button>
                </div>

                {gallery.length + pendingImages.length === 0 ? (
                  <p className="p-6 text-center text-gray-500 bg-[#F8F6F0] rounded-xl border border-dashed">
                    {t("product_editor.empty_gallery")}
                  </p>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {gallery.map((img: any) => (
                      <div key={img.id} className="rounded-xl border border-gray-200 overflow-hidden bg-white group">
                        <div className="h-28 bg-gray-50 flex items-center justify-center overflow-hidden">
                          <img src={img.image_url} alt={img.alt_text || ""} className="w-full h-full object-cover" />
                        </div>
                        <div className="p-2 space-y-1">
                          <p className="text-[10px] font-mono text-gray-500 truncate" title={img.image_url}>
                            {img.image_url}
                          </p>
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => setPrimaryImage(img.image_url)}
                              className="flex-1 px-1.5 py-1 rounded-lg bg-[#F8F6F0] border border-[#D4AF62]/40 font-bold text-[10px] text-[#063D2E]"
                            >
                              {draft.main_image_url === img.image_url ? t("product_editor.is_primary") : t("product_editor.btn_set_primary")}
                            </button>
                            <button
                              type="button"
                              onClick={() => removeGalleryImage(img.id)}
                              disabled={galleryBusy === img.id}
                              className="p-1 rounded-lg bg-red-50 text-red-700 border border-red-200"
                            >
                              {galleryBusy === img.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                    {pendingImages.map((url) => (
                      <div key={url} className="rounded-xl border border-dashed border-amber-300 overflow-hidden bg-amber-50/40">
                        <div className="h-28 bg-white flex items-center justify-center overflow-hidden">
                          <img src={url} alt="" className="w-full h-full object-cover" />
                        </div>
                        <div className="p-2 space-y-1">
                          <p className="text-[10px] font-bold text-amber-800">{t("product_editor.pending_image_note")}</p>
                          <button
                            type="button"
                            onClick={() => setPendingImages((prev) => prev.filter((u) => u !== url))}
                            className="w-full px-1.5 py-1 rounded-lg bg-white border border-rose-200 text-rose-700 font-bold text-[10px]"
                          >
                            {t("product_editor.remove_image")}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <input
                    placeholder={t("product_editor.paste_url_placeholder")}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        const value = (e.target as HTMLInputElement).value.trim();
                        if (value) {
                          void addGalleryImage(value);
                          (e.target as HTMLInputElement).value = "";
                        }
                      }
                    }}
                    className="flex-1 px-3 py-2 border rounded-xl bg-white font-mono"
                  />
                  <span className="text-[10px] text-gray-400">{t("product_editor.press_enter_to_add")}</span>
                </div>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleUpload(file, "main");
                  e.target.value = "";
                }}
              />
              <input
                ref={galleryInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleUpload(file, "gallery");
                  e.target.value = "";
                }}
              />
            </div>
          )}

          {/* ---------------- SEO & LOGISTICS ---------------- */}
          {tab === "seo" && (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl border border-[#D4AF62]/40 space-y-3">
                <p className="font-bold text-[#063D2E]">{t("product_editor.seo_heading")}</p>
                <div>
                  <label className="block font-semibold mb-1">{t("product_editor.seo_title_label")}</label>
                  <input
                    maxLength={255}
                    value={draft.seo_title}
                    onChange={(e) => patch({ seo_title: e.target.value })}
                    placeholder={draft.name_fr || "Titre affiché dans Google"}
                    className="w-full px-3 py-2 border rounded-xl bg-white"
                  />
                </div>
                <div>
                  <label className="block font-semibold mb-1">{t("product_editor.seo_desc_label")}</label>
                  <textarea
                    rows={3}
                    maxLength={320}
                    value={draft.seo_description}
                    onChange={(e) => patch({ seo_description: e.target.value })}
                    placeholder="Résumé accrocheur affiché dans les résultats de recherche"
                    className="w-full px-3 py-2 border rounded-xl bg-white"
                  />
                  <p className="text-[10px] text-gray-400 mt-1">{t("product_editor.seo_desc_chars", { count: draft.seo_description.length })}</p>
                </div>
                <div>
                  <label className="block font-semibold mb-1">{t("product_editor.tags_label")}</label>
                  <input
                    value={draft.tags}
                    onChange={(e) => patch({ tags: e.target.value })}
                    placeholder="sac cuir, maroquinerie, luxe algérien"
                    className="w-full px-3 py-2 border rounded-xl bg-white"
                  />
                </div>
                <div className="p-3 rounded-xl bg-[#F8F6F0] border border-gray-200">
                  <p className="text-[10px] uppercase tracking-wide text-gray-500 font-bold mb-1">{t("product_editor.google_preview")}</p>
                  <p className="text-[#1a0dab] font-semibold truncate">{draft.seo_title || draft.name_fr || "Titre du produit"}</p>
                  <p className="text-emerald-700 text-[11px] font-mono truncate">mus-luxury.com/produit/{draft.slug || "slug-produit"}</p>
                  <p className="text-gray-600 line-clamp-2">
                    {draft.seo_description || draft.description_fr || "Ajoutez une meta description pour améliorer le référencement."}
                  </p>
                </div>
              </div>

              <div className="p-4 rounded-2xl border border-[#D4AF62]/40 space-y-3">
                <p className="font-bold text-[#063D2E]">{t("product_editor.logistics_heading")}</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold mb-1">{t("product_editor.weight_label")}</label>
                    <input
                      type="number"
                      min={0}
                      value={draft.weight_grams}
                      onChange={(e) => patch({ weight_grams: e.target.value === "" ? "" : Math.max(0, Number(e.target.value)) })}
                      placeholder="900"
                      className="w-full px-3 py-2 border rounded-xl bg-white font-mono"
                    />
                    <p className="text-[10px] text-gray-500 mt-1">{t("product_editor.weight_hint")}</p>
                  </div>
                  <div>
                    <label className="block font-semibold mb-1">{t("product_editor.dimensions_label")}</label>
                    <input
                      value={draft.dimensions_cm}
                      onChange={(e) => patch({ dimensions_cm: e.target.value })}
                      placeholder="30 x 20 x 10"
                      className="w-full px-3 py-2 border rounded-xl bg-white font-mono"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
            </div>

            {/* Live Storefront Preview Column */}
            {showLivePreview && (
              <div className="lg:col-span-4 sticky top-0 space-y-3">
                <LiveProductCardPreview
                  name={draft.name_fr}
                  brandName={localBrands.find((b) => b.id === Number(draft.brand_id))?.name}
                  categoryName={category?.name_fr}
                  mainImageUrl={draft.main_image_url}
                  sellingPriceDzd={draft.selling_price_dzd}
                  previousPriceDzd={draft.previous_price_dzd}
                  discountPercent={draft.discount_percent}
                  isFeatured={draft.is_featured}
                  isNewArrival={draft.is_new_arrival}
                  variants={draft.variants}
                />
                <div className="p-3 rounded-2xl bg-[#063D2E]/5 border border-[#D4AF62]/30 text-[11px] text-[#063D2E] space-y-1">
                  <div className="flex justify-between font-bold">
                    <span>Marge unitaire estimée :</span>
                    <span className={margin >= 0 ? "text-emerald-700" : "text-rose-700"}>
                      {margin >= 0 ? "+" : ""}{margin} DZD ({marginPct.toFixed(0)}%)
                    </span>
                  </div>
                  <div className="flex justify-between text-gray-500">
                    <span>Coût d'achat fournisseur :</span>
                    <span>{draft.purchase_cost_dzd || 0} DZD</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-[#F8F6F0] border-t border-[#D4AF62]/40 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-[11px] text-gray-600">
            {dirty ? (
              <>
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                <span>{t("product_editor.sync_status_dirty")}</span>
              </>
            ) : (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-600" />
                <span>{t("product_editor.sync_status_synced")}</span>
              </>
            )}
            <ChevronRight className="w-3 h-3 text-gray-300" />
            <span>{t("product_editor.variants_count", { count: draft.variants.length })}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={requestClose}
              className="px-4 py-2 rounded-xl bg-white border border-gray-300 font-bold text-gray-700"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl bg-gradient-to-r from-[#D4AF62] to-[#E8D4A5] text-[#02291F] font-extrabold shadow-xs hover:brightness-105 transition disabled:opacity-60"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              <span>{isCreate ? t("product_editor.btn_submit_create") : t("product_editor.btn_submit_save")}</span>
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
