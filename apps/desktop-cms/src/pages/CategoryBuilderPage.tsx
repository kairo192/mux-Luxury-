import { readDraft, writeDraft, clearDraft } from "../utils/draftStorage";
import React, { useEffect, useState } from "react";
import { useT } from "../i18n";
import { DesktopCmsApi } from "../api/adminClient";
import { confirmClientAction, notifyClientError, notifyClientSuccess, notifyClientWarning } from "../utils/clientNotifier";
import {
  Tags,
  Plus,
  Search,
  Eye,
  Sparkles,
  Check,
  X,
  Layers,
  SlidersHorizontal,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";

import type { CategoryPreset, DraftAttribute, DraftAttributeOption } from "./categoryBuilder/catalogSetup";
import { CATEGORY_PRESETS } from "./categoryBuilder/presets";
import { CategoryCreateForm } from "./categoryBuilder/CategoryCreateForm";
import { CategoryCardsGrid } from "./categoryBuilder/CategoryCardsGrid";
import { EditCategoryModal } from "./categoryBuilder/EditCategoryModal";
import { DeleteCategoryModal } from "./categoryBuilder/DeleteCategoryModal";
import { QuickAttributeModal } from "./categoryBuilder/QuickAttributeModal";
import { pickLang } from "../i18n/translations";

// Kept importable from here (older imports).
export type { CategoryPreset, DraftAttribute, DraftAttributeOption } from "./categoryBuilder/catalogSetup";
export { CATEGORY_PRESETS } from "./categoryBuilder/presets";


export function CategoryBuilderPage({ onCategoryChanged }: { onCategoryChanged?: () => void }) {
  const t = useT();
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusMsg, setStatusMsg] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | "active" | "homepage" | "with_attrs" | "archived">("all");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [activePresetId, setActivePresetId] = useState<string | null>(null);

  // New Category Creation Drafts
  const [nameFr, setNameFr] = useState(() => readDraft("luxe_cat_draft_name_fr", ""));
  const [nameAr, setNameAr] = useState(() => readDraft("luxe_cat_draft_name_ar", ""));
  const [nameEn, setNameEn] = useState(() => readDraft("luxe_cat_draft_name_en", ""));
  const [slug, setSlug] = useState(() => readDraft("luxe_cat_draft_slug", ""));
  const [descriptionFr, setDescriptionFr] = useState(() => readDraft("luxe_cat_draft_desc", ""));
  const [displayOrder, setDisplayOrder] = useState(() => readDraft("luxe_cat_draft_order", 10));
  const [imageUrl, setImageUrl] = useState(() => readDraft("luxe_cat_draft_img", ""));
  const [bannerUrl, setBannerUrl] = useState(() => readDraft("luxe_cat_draft_banner", ""));

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

  // Dynamic Attributes Draft
  const [attributes, setAttributes] = useState<DraftAttribute[]>(() =>
    readDraft("luxe_cat_draft_attrs", [
      {
        attr_key: "color",
        label_fr: "Couleur",
        label_ar: "اللون",
        label_en: "Color",
        input_type: "color",
        unit: "",
        is_required: false,
        is_visible_on_storefront: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "Noir, Blanc, Beige, Marron",
        rich_options: [
          { value: "Noir", label_fr: "Noir", color_hex: "#0A0A0A", display_order: 1 },
          { value: "Blanc", label_fr: "Blanc", color_hex: "#FFFFFF", display_order: 2 },
          { value: "Beige", label_fr: "Beige", color_hex: "#D9C7A7", display_order: 3 },
          { value: "Marron", label_fr: "Marron", color_hex: "#6B4226", display_order: 4 },
        ],
      },
      {
        attr_key: "size",
        label_fr: "Taille",
        label_ar: "المقاس",
        label_en: "Size",
        input_type: "size",
        unit: "",
        is_required: false,
        is_visible_on_storefront: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "XS, S, M, L, XL, XXL",
      },
      {
        attr_key: "material",
        label_fr: "Matière",
        label_ar: "المادة",
        label_en: "Material",
        input_type: "short_text",
        unit: "",
        is_required: false,
        is_visible_on_storefront: true,
        is_filterable: true,
        is_variant_axis: false,
        options_csv: "",
      },
    ])
  );

  useEffect(() => {
    writeDraft("luxe_cat_draft_attrs", attributes);
  }, [attributes]);

  // Sub-builder states for adding an attribute
  const [newKey, setNewKey] = useState("");
  const [newLabelFr, setNewLabelFr] = useState("");
  const [newLabelAr, setNewLabelAr] = useState("");
  const [newLabelEn, setNewLabelEn] = useState("");
  const [newType, setNewType] = useState("short_text");
  const [newUnit, setNewUnit] = useState("");
  const [newRequired, setNewRequired] = useState(false);
  const [newVisibleOnStorefront, setNewVisibleOnStorefront] = useState(true);
  const [newFilterable, setNewFilterable] = useState(true);
  const [newVariantAxis, setNewVariantAxis] = useState(false);
  const [newOptionsCsv, setNewOptionsCsv] = useState("");
  const [newRichColors, setNewRichColors] = useState<DraftAttributeOption[]>([]);
  const [tempColorName, setTempColorName] = useState("");
  const [tempColorHex, setTempColorHex] = useState("#063D2E");

  // Edit Modal State
  const [editingCategory, setEditingCategory] = useState<any | null>(null);
  const [editNameFr, setEditNameFr] = useState("");
  const [editNameAr, setEditNameAr] = useState("");
  const [editNameEn, setEditNameEn] = useState("");
  const [editSlug, setEditSlug] = useState("");
  const [editDescFr, setEditDescFr] = useState("");
  const [editImageUrl, setEditImageUrl] = useState("");
  const [editBannerUrl, setEditBannerUrl] = useState("");
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

  async function handleInitializeLuxuryStarterCollections() {
    setLoading(true);
    setError("");
    setStatusMsg("");
    try {
      for (const preset of CATEGORY_PRESETS.slice(0, 4)) {
        const catPayload = {
          slug: preset.slug,
          name_fr: preset.name,
          name_ar: preset.name_ar,
          name_en: preset.name_en,
          description_fr: preset.description_fr,
          description_ar: preset.description_ar,
          description_en: preset.description_en,
          display_order: 1,
          is_active: true,
          show_on_homepage: true,
          image_url: preset.image_url,
          banner_url: preset.banner_url,
          attributes: preset.attributes.map((attr, idx) => ({
            attr_key: attr.attr_key,
            label_fr: attr.label_fr,
            label_ar: attr.label_ar || attr.label_fr,
            label_en: attr.label_en || attr.label_fr,
            input_type: attr.input_type,
            unit: attr.unit || "",
            is_required: false,
            is_visible_on_storefront: Boolean(attr.is_visible_on_storefront),
            is_filterable: Boolean(attr.is_filterable),
            is_variant_axis: Boolean(attr.is_variant_axis),
            display_order: idx + 1,
            options: (attr.rich_options && attr.rich_options.length > 0)
              ? attr.rich_options.map((o, oIdx) => ({
                  value: o.value,
                  label_fr: o.label_fr || o.value,
                  label_ar: o.label_ar || o.value,
                  label_en: o.label_en || o.value,
                  color_hex: o.color_hex || null,
                  display_order: oIdx + 1,
                }))
              : attr.options_csv
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean)
                  .map((val, oIdx) => ({
                    value: val,
                    label_fr: val,
                    label_ar: val,
                    label_en: val,
                    color_hex: null,
                    display_order: oIdx + 1,
                  })),
          })),
        };
        await DesktopCmsApi.createCategory(catPayload);
      }
      notifyClientSuccess(t("cb.init_ok_title"), t("cb.init_ok_body"));
      setStatusMsg(t("cb.init_ok_status"));
      await loadCategories();
      onCategoryChanged?.();
    } catch (err: any) {
      notifyClientError(err, t("cb.init_failed"));
      setError(err?.message || t("cb.init_error"));
    } finally {
      setLoading(false);
    }
  }

  async function loadCategories() {
    setLoading(true);
    setError("");
    try {
      // Admin list incl. archived ones (shown only in the "Archivées" tab).
      const res = await DesktopCmsApi.listCategories(true);
      setCategories(res.items || []);
    } catch (err: any) {
      const tr = notifyClientError(err, t("cb.load_failed"), false);
      setError(tr.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCategories();
  }, []);

  function applyCategoryPreset(preset: CategoryPreset) {
    setActivePresetId(preset.id);
    setNameFr(preset.name);
    setNameAr(preset.name_ar);
    setNameEn(preset.name_en);
    setSlug(preset.slug);
    setDescriptionFr(preset.description_fr);
    setImageUrl(preset.image_url);
    setBannerUrl(preset.banner_url);
    setAttributes(JSON.parse(JSON.stringify(preset.attributes)));
    notifyClientSuccess(
      t("cb.preset_applied_title"),
      t("cb.preset_applied_body", { name: pickLang(preset, "name"), n: preset.attributes.length })
    );
  }

  function addColorToRichList() {
    if (!tempColorName.trim()) {
      notifyClientWarning(t("cb.color_name_missing_title"), t("cb.color_name_missing_body"));
      return;
    }
    const cleanName = tempColorName.trim();
    if (newRichColors.some((c) => c.value.toLowerCase() === cleanName.toLowerCase())) {
      notifyClientWarning(t("cb.color_exists_title"), t("cb.color_exists_body"));
      return;
    }
    const updated = [
      ...newRichColors,
      {
        value: cleanName,
        label_fr: cleanName,
        label_ar: cleanName,
        label_en: cleanName,
        color_hex: tempColorHex,
        display_order: newRichColors.length + 1,
      },
    ];
    setNewRichColors(updated);
    setNewOptionsCsv(updated.map((c) => c.value).join(", "));
    setTempColorName("");
  }

  function removeColorFromRichList(val: string) {
    const updated = newRichColors.filter((c) => c.value !== val);
    setNewRichColors(updated);
    setNewOptionsCsv(updated.map((c) => c.value).join(", "));
  }

  function addDraftAttribute() {
    const cleanKey = newKey.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_");
    if (!cleanKey || !newLabelFr.trim()) {
      notifyClientWarning(
        t("cb.attr_incomplete_title"),
        t("cb.attr_incomplete_body")
      );
      return;
    }
    if (attributes.some((a) => a.attr_key === cleanKey)) {
      notifyClientWarning(
        t("cb.attr_key_exists_title"),
        t("cb.attr_key_exists_body", { key: cleanKey })
      );
      return;
    }

    const isColor = newType === "color" || cleanKey === "color" || cleanKey.includes("couleur");
    const richOpts = isColor && newRichColors.length > 0 ? [...newRichColors] : undefined;

    setAttributes((prev) => [
      ...prev,
      {
        attr_key: cleanKey,
        label_fr: newLabelFr.trim(),
        label_ar: (newLabelAr || newLabelFr).trim(),
        label_en: (newLabelEn || newLabelFr).trim(),
        input_type: newType,
        unit: newUnit.trim(),
        is_required: false,
        is_visible_on_storefront: newVisibleOnStorefront,
        is_filterable: newFilterable,
        is_variant_axis: newVariantAxis,
        options_csv: newOptionsCsv,
        rich_options: richOpts,
      },
    ]);

    setNewKey("");
    setNewLabelFr("");
    setNewLabelAr("");
    setNewLabelEn("");
    setNewUnit("");
    setNewOptionsCsv("");
    setNewRichColors([]);
    setNewRequired(false);
    setNewVisibleOnStorefront(true);
    setNewFilterable(true);
    setNewVariantAxis(false);

    notifyClientSuccess(t("cb.attr_added_title"), t("cb.attr_added_model", { name: newLabelFr.trim() }));
  }

  function removeDraftAttribute(idx: number) {
    setAttributes((prev) => prev.filter((_, i) => i !== idx));
  }

  function moveDraftAttribute(idx: number, dir: "up" | "down") {
    setAttributes((prev) => {
      const next = [...prev];
      const targetIdx = dir === "up" ? idx - 1 : idx + 1;
      if (targetIdx < 0 || targetIdx >= next.length) return prev;
      const temp = next[idx];
      next[idx] = next[targetIdx];
      next[targetIdx] = temp;
      return next;
    });
  }

  async function handleSaveCategory(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setStatusMsg("");
    if (nameFr.trim().length < 2 || slug.trim().length < 2) {
      notifyClientWarning(
        t("cb.info_incomplete_title"),
        t("cb.info_incomplete_body")
      );
      return;
    }

    try {
      const formattedAttrs = attributes.map((attr, idx) => {
        let opts: any[] = [];
        if (attr.rich_options && attr.rich_options.length > 0) {
          opts = attr.rich_options.map((o, oIdx) => ({
            value: o.value,
            label_fr: o.label_fr || o.value,
            label_ar: o.label_ar || o.value,
            label_en: o.label_en || o.value,
            color_hex: o.color_hex || null,
            display_order: oIdx + 1,
          }));
        } else {
          opts = attr.options_csv
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
            .map((val, oIdx) => ({
              value: val,
              label_fr: val,
              label_ar: val,
              label_en: val,
              color_hex: null,
              display_order: oIdx + 1,
            }));
        }

        return {
          attr_key: attr.attr_key,
          label_fr: attr.label_fr,
          label_ar: attr.label_ar || attr.label_fr,
          label_en: attr.label_en || attr.label_fr,
          input_type: attr.input_type,
          unit: attr.unit || "",
          is_required: false,
          is_visible_on_storefront: Boolean(attr.is_visible_on_storefront),
          is_filterable: Boolean(attr.is_filterable),
          is_variant_axis: Boolean(attr.is_variant_axis),
          display_order: idx + 1,
          options: opts,
        };
      });

      const payload = {
        slug: slug.trim().toLowerCase(),
        name_fr: nameFr.trim(),
        name_ar: (nameAr || nameFr).trim(),
        name_en: (nameEn || nameFr).trim(),
        description_fr: descriptionFr.trim(),
        image_url: imageUrl,
        banner_url: bannerUrl,
        display_order: Number(displayOrder) || 10,
        is_active: true,
        show_on_homepage: true,
        attributes: formattedAttrs,
      };

      await DesktopCmsApi.createCategory(payload);

      const okMsg = t("cb.created_msg", { name: nameFr, n: formattedAttrs.length });
      setStatusMsg(okMsg);
      notifyClientSuccess(t("cb.published_title"), okMsg);

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
      setActivePresetId(null);
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, t("cb.create_failed"));
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
    setEditImageUrl(cat.image_url || "");
    setEditBannerUrl(cat.banner_url || "");
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
        image_url: editImageUrl,
        banner_url: editBannerUrl,
        display_order: Number(editOrder) || 1,
        is_active: editIsActive,
        show_on_homepage: editShowHomepage,
      });

      notifyClientSuccess(
        t("cb.updated_title"),
        t("cb.updated_body", { name: editNameFr })
      );
      setEditingCategory(null);
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, t("cb.update_failed"));
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
      const msg = t("cb.homepage_toggled", { name: pickLang(cat, "name") });
      setStatusMsg(msg);
      notifyClientSuccess(t("cb.updated_title"), msg);
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, t("cb.update_failed"));
      setError(tr.message);
    }
  }

  // Restore an archived category
  async function handleRestoreCategory(catId: number, catName: string) {
    setError("");
    try {
      await DesktopCmsApi.restoreCategory(catId);
      const msg = t("cb.restored_msg", { name: catName });
      setStatusMsg(msg);
      notifyClientSuccess(t("cb.restored_title"), msg);
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, t("cb.restore_failed"));
      setError(tr.message);
    }
  }

  // Archive (Soft Delete) Category
  async function handleArchiveCategory(catId: number, catName: string) {
    setError("");
    try {
      await DesktopCmsApi.archiveCategory(catId);
      const msg = t("cb.archived_msg", { name: catName });
      setStatusMsg(msg);
      notifyClientSuccess(t("cb.archived_title"), msg);
      setDeletingCategory(null);
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, t("cb.archive_failed"));
      setError(tr.message);
    }
  }

  // Permanent (Hard Delete) Category
  async function handlePermanentDeleteCategory(catId: number, catName: string) {
    setIsDeleting(true);
    setError("");
    try {
      await DesktopCmsApi.deleteCategory(catId, true);
      const msg = t("cb.deleted_msg", { name: catName });
      setStatusMsg(msg);
      notifyClientSuccess(t("cb.deleted_title"), msg);
      setDeletingCategory(null);
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, t("cb.delete_failed"));
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
        t("cb.attr_deleted_title"),
        t("cb.attr_deleted_body")
      );
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      if (err?.status === 409) {
        // The server explains why (used by N products / defines variants).
        const reason = String(err?.userMessage || err?.message || "");
        if (/variante|variant|متغير/i.test(reason)) {
          notifyClientWarning(t("cb.attr_used_variants"), reason);
          setError(reason);
          return;
        }
        const ok = await confirmClientAction({
          title: t("cb.attr_delete_title"),
          message: reason || t("cb.attr_delete_body"),
          confirmLabel: t("cb.attr_delete_confirm"),
          danger: true,
        });
        if (!ok) return;
        try {
          await DesktopCmsApi.deleteCategoryAttribute(attrId, true);
          notifyClientSuccess(t("cb.attr_deleted_title"), t("cb.attr_deleted_values"));
          await loadCategories();
          if (onCategoryChanged) onCategoryChanged();
          return;
        } catch (innerErr: any) {
          const trInner = notifyClientError(innerErr, t("cb.attr_delete_refused"));
          setError(trInner.message);
          return;
        }
      }
      const tr = notifyClientError(err, t("cb.attr_delete_refused"));
      setError(tr.message);
    }
  }

  // Add Attribute to Existing Category
  async function handleAddAttributeToExisting(e: React.FormEvent) {
    e.preventDefault();
    if (!quickAttrCategory) return;
    const cleanKey = quickAttrKey.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_");
    if (!cleanKey || !quickAttrLabelFr.trim()) {
      notifyClientWarning(t("cb.required_title"), t("cb.required_body"));
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
        is_required: false,
        is_filterable: quickAttrFilterable,
        is_variant_axis: quickAttrVariant,
        display_order: (quickAttrCategory.attributes || []).length + 1,
        options: parsedOptions,
      });

      notifyClientSuccess(
        t("cb.attr_added_title"),
        t("cb.attr_added_cat", { name: quickAttrLabelFr, cat: pickLang(quickAttrCategory, "name") })
      );
      setQuickAttrCategory(null);
      setQuickAttrKey("");
      setQuickAttrLabelFr("");
      setQuickAttrOptions("");
      await loadCategories();
      if (onCategoryChanged) onCategoryChanged();
    } catch (err: any) {
      const tr = notifyClientError(err, t("cb.attr_add_failed"));
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

    const archived = Boolean(c.deleted_at);
    if (activeFilter === "archived") return archived;
    if (archived) return false;
    if (activeFilter === "active") return c.is_active;
    if (activeFilter === "homepage") return c.show_on_homepage;
    if (activeFilter === "with_attrs") return (c.attributes || []).length > 0;
    return true;
  });

  const totalAttributesCount = categories.reduce(
    (acc, cat) => acc + (cat.attributes ? cat.attributes.length : 0),
    0
  );
  const liveCategories = categories.filter((c) => !c.deleted_at);
  const archivedCount = categories.length - liveCategories.length;
  const homepageCount = liveCategories.filter((c) => c.show_on_homepage).length;
  // Real figure instead of a fixed "OK" badge: categories customers cannot see.
  const hiddenCount = liveCategories.filter((c) => !c.is_active).length;

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
                {t("cat_builder.title")}
              </h1>
              <p className="text-xs text-gray-500 mt-0.5">
                {t("cat_builder.subtitle")}
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
            <span>{t("cat_builder.btn_refresh")}</span>
          </button>
          <button
            type="button"
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62] text-xs font-extrabold hover:bg-[#02291F] shadow-sm transition"
          >
            <Plus className="w-4 h-4" />
            <span>{showCreateForm ? t("cat_builder.btn_close_config") : t("cat_builder.btn_create_category")}</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-white rounded-xl border border-[#D4AF62]/30 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] text-gray-500 font-bold uppercase">{t("cat_builder.kpi_total")}</span>
            <p className="text-2xl font-bold font-mono text-[#063D2E] mt-0.5">{liveCategories.length}</p>
          </div>
          <div className="p-3 rounded-xl bg-[#F8F6F0] text-[#063D2E]">
            <Layers className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-[#D4AF62]/30 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] text-gray-500 font-bold uppercase">{t("cat_builder.kpi_homepage")}</span>
            <p className="text-2xl font-bold font-mono text-emerald-700 mt-0.5">{homepageCount}</p>
          </div>
          <div className="p-3 rounded-xl bg-emerald-50 text-emerald-800">
            <Eye className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-[#D4AF62]/30 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] text-gray-500 font-bold uppercase">{t("cat_builder.kpi_active_attrs")}</span>
            <p className="text-2xl font-bold font-mono text-amber-700 mt-0.5">{totalAttributesCount}</p>
          </div>
          <div className="p-3 rounded-xl bg-amber-50 text-amber-800">
            <SlidersHorizontal className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-[#D4AF62]/30 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] text-gray-500 font-bold uppercase">{t("cat_builder.kpi_hidden")}</span>
            <p className={`text-2xl font-bold font-mono mt-0.5 ${hiddenCount ? "text-amber-700" : "text-emerald-700"}`}>{hiddenCount}</p>
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
          <button aria-label={t("cb.hide_message")} onClick={() => setStatusMsg("")} className="text-emerald-800 font-bold hover:opacity-75 transition">
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
          <button aria-label={t("cb.hide_message")} onClick={() => setError("")} className="text-red-800 font-bold hover:opacity-75 transition">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Upgraded Category Creation Form with Presets & Live Storefront Preview */}
      {showCreateForm && (
        <CategoryCreateForm
          handleSaveCategory={handleSaveCategory}
          setShowCreateForm={setShowCreateForm}
          activePresetId={activePresetId}
          applyCategoryPreset={applyCategoryPreset}
          nameFr={nameFr}
          setNameFr={setNameFr}
          slug={slug}
          setSlug={setSlug}
          nameAr={nameAr}
          setNameAr={setNameAr}
          nameEn={nameEn}
          setNameEn={setNameEn}
          descriptionFr={descriptionFr}
          setDescriptionFr={setDescriptionFr}
          displayOrder={displayOrder}
          setDisplayOrder={setDisplayOrder}
          imageUrl={imageUrl}
          setImageUrl={setImageUrl}
          bannerUrl={bannerUrl}
          setBannerUrl={setBannerUrl}
          attributes={attributes}
          moveDraftAttribute={moveDraftAttribute}
          removeDraftAttribute={removeDraftAttribute}
          newKey={newKey}
          setNewKey={setNewKey}
          newLabelFr={newLabelFr}
          setNewLabelFr={setNewLabelFr}
          newType={newType}
          setNewType={setNewType}
          newUnit={newUnit}
          setNewUnit={setNewUnit}
          setTempColorName={setTempColorName}
          setTempColorHex={setTempColorHex}
          tempColorHex={tempColorHex}
          tempColorName={tempColorName}
          addColorToRichList={addColorToRichList}
          newRichColors={newRichColors}
          removeColorFromRichList={removeColorFromRichList}
          setNewOptionsCsv={setNewOptionsCsv}
          newOptionsCsv={newOptionsCsv}
          newVariantAxis={newVariantAxis}
          setNewVariantAxis={setNewVariantAxis}
          newFilterable={newFilterable}
          setNewFilterable={setNewFilterable}
          newVisibleOnStorefront={newVisibleOnStorefront}
          setNewVisibleOnStorefront={setNewVisibleOnStorefront}
          newRequired={newRequired}
          setNewRequired={setNewRequired}
          addDraftAttribute={addDraftAttribute}
        />
      )}


      {/* Categories Toolbar: Search & Filters */}
      <div className="bg-white p-4 rounded-2xl border border-[#D4AF62]/30 shadow-sm flex flex-col md:flex-row items-center justify-between gap-3 text-xs">
        <div className="relative w-full md:w-96">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t("cat_builder.search_placeholder")}
            className="w-full pl-9 pr-3 py-2 border rounded-xl bg-[#F8F6F0] focus:bg-white focus:border-[#063D2E] outline-none transition"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          {[
            { id: "all", label: t("cat_builder.tab_all", { count: liveCategories.length }) },
            { id: "homepage", label: t("cat_builder.tab_homepage", { count: homepageCount }) },
            { id: "with_attrs", label: t("cat_builder.tab_with_attrs") },
            ...(archivedCount > 0 ? [{ id: "archived", label: t("cat_builder.tab_archived", { count: archivedCount }) }] : []),
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
      <CategoryCardsGrid
        loading={loading}
        filteredCategories={filteredCategories}
        liveCategories={liveCategories}
        activeFilter={activeFilter}
        handleInitializeLuxuryStarterCollections={handleInitializeLuxuryStarterCollections}
        setShowCreateForm={setShowCreateForm}
        setSearchQuery={setSearchQuery}
        setActiveFilter={setActiveFilter}
        setQuickAttrCategory={setQuickAttrCategory}
        handleDeleteAttribute={handleDeleteAttribute}
        handleRestoreCategory={handleRestoreCategory}
        setDeletingCategory={setDeletingCategory}
        handleToggleCategoryHomepage={handleToggleCategoryHomepage}
        handleOpenEdit={handleOpenEdit}
      />

      {/* EDIT CATEGORY MODAL */}
      {editingCategory && (
        <EditCategoryModal
          editingCategory={editingCategory}
          setEditingCategory={setEditingCategory}
          handleSubmitEdit={handleSubmitEdit}
          editNameFr={editNameFr}
          setEditNameFr={setEditNameFr}
          editNameAr={editNameAr}
          setEditNameAr={setEditNameAr}
          editNameEn={editNameEn}
          setEditNameEn={setEditNameEn}
          editSlug={editSlug}
          setEditSlug={setEditSlug}
          editOrder={editOrder}
          setEditOrder={setEditOrder}
          editDescFr={editDescFr}
          setEditDescFr={setEditDescFr}
          editImageUrl={editImageUrl}
          setEditImageUrl={setEditImageUrl}
          editBannerUrl={editBannerUrl}
          setEditBannerUrl={setEditBannerUrl}
          editIconKey={editIconKey}
          setEditIconKey={setEditIconKey}
          editShowHomepage={editShowHomepage}
          setEditShowHomepage={setEditShowHomepage}
          editIsActive={editIsActive}
          setEditIsActive={setEditIsActive}
          savingEdit={savingEdit}
        />
      )}

      {/* DELETE / ARCHIVE MODAL */}
      {deletingCategory && (
        <DeleteCategoryModal
          deletingCategory={deletingCategory}
          handleArchiveCategory={handleArchiveCategory}
          isDeleting={isDeleting}
          handlePermanentDeleteCategory={handlePermanentDeleteCategory}
          setDeletingCategory={setDeletingCategory}
        />
      )}

      {/* QUICK ADD ATTRIBUTE MODAL */}
      {quickAttrCategory && (
        <QuickAttributeModal
          quickAttrCategory={quickAttrCategory}
          setQuickAttrCategory={setQuickAttrCategory}
          handleAddAttributeToExisting={handleAddAttributeToExisting}
          quickAttrKey={quickAttrKey}
          setQuickAttrKey={setQuickAttrKey}
          quickAttrLabelFr={quickAttrLabelFr}
          setQuickAttrLabelFr={setQuickAttrLabelFr}
          quickAttrType={quickAttrType}
          setQuickAttrType={setQuickAttrType}
          quickAttrOptions={quickAttrOptions}
          setQuickAttrOptions={setQuickAttrOptions}
          quickAttrVariant={quickAttrVariant}
          setQuickAttrVariant={setQuickAttrVariant}
          quickAttrFilterable={quickAttrFilterable}
          setQuickAttrFilterable={setQuickAttrFilterable}
          quickAttrRequired={quickAttrRequired}
          setQuickAttrRequired={setQuickAttrRequired}
          savingQuickAttr={savingQuickAttr}
        />
      )}
    </div>
  );
}
