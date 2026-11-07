# scratch/generate_upgraded_category_page.py
import re

with open('apps/desktop-cms/src/pages/CategoryBuilderPage.tsx', 'r', encoding='utf-8') as f:
    orig = f.read()

cut_toolbar = '{/* Categories Toolbar: Search & Filters */}'
if cut_toolbar not in orig:
    raise Exception("cut_toolbar not found!")

table_and_modals_jsx = cut_toolbar + orig.split(cut_toolbar)[1]

with open('scratch/upgrade_category_builder.py', 'r', encoding='utf-8') as f:
    header_and_presets = f.read().split("code = '''")[1].rsplit("'''")[0]

component_code = '''
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
  const [chosenIconKey, setChosenIconKey] = useState("bag");
  const [imageUrl, setImageUrl] = useState(() => readDraft("luxe_cat_draft_img", "/assets/cat_vetements.jpg"));
  const [bannerUrl, setBannerUrl] = useState(() => readDraft("luxe_cat_draft_banner", "/assets/hero_bag_clean.jpg"));

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
        is_required: true,
        is_visible_on_storefront: true,
        is_filterable: true,
        is_variant_axis: true,
        options_csv: "Noir Profond, Blanc Pur, Vert Émeraude Mus, Bordeaux Royal",
        rich_options: [
          { value: "Noir Profond", label_fr: "Noir Profond", color_hex: "#0A0A0A", display_order: 1 },
          { value: "Blanc Pur", label_fr: "Blanc Pur", color_hex: "#FFFFFF", display_order: 2 },
          { value: "Vert Émeraude Mus", label_fr: "Vert Émeraude Mus", color_hex: "#063D2E", display_order: 3 },
          { value: "Bordeaux Royal", label_fr: "Bordeaux Royal", color_hex: "#4A0E17", display_order: 4 },
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
        input_type: "single_select",
        unit: "",
        is_required: true,
        is_visible_on_storefront: true,
        is_filterable: true,
        is_variant_axis: false,
        options_csv: "100% Coton Pima, Lin Naturel, Soie Noble",
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
  const [tempColorName, setTempColorName] = useState("Vert Émeraude Mus");
  const [tempColorHex, setTempColorHex] = useState("#063D2E");

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

  async function handleInitializeLuxuryStarterCollections() {
    setLoading(true);
    setError("");
    setStatusMsg("");
    try {
      for (const preset of CATEGORY_PRESETS.slice(0, 4)) {
        const catPayload = {
          slug: preset.slug,
          name_fr: preset.name,
          name_ar: preset.slug === "t-shirts" ? "قمصان وملابس فاخرة" : preset.name,
          name_en: preset.name,
          description_fr: preset.description_fr,
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
            is_required: Boolean(attr.is_required),
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
      notifyClientSuccess("Collections créées", "Les collections de prestige Mus Luxury ont été initialisées avec leurs attributs.");
      setStatusMsg("Les collections Mus Luxury ont été configurées avec succès.");
      await loadCategories();
      onCategoryChanged?.();
    } catch (err: any) {
      notifyClientError(err, "Initialisation impossible");
      setError(err?.message || "Erreur lors de l'initialisation des collections.");
    } finally {
      setLoading(false);
    }
  }

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

  useEffect(() => {
    loadCategories();
  }, []);

  function applyCategoryPreset(preset: CategoryPreset) {
    setActivePresetId(preset.id);
    setNameFr(preset.name);
    setNameAr(preset.slug === "t-shirts" ? "قمصان وملابس فاخرة" : preset.name);
    setNameEn(preset.name);
    setSlug(preset.slug);
    setDescriptionFr(preset.description_fr);
    setImageUrl(preset.image_url);
    setBannerUrl(preset.banner_url);
    setChosenIconKey(preset.iconName);
    setAttributes(JSON.parse(JSON.stringify(preset.attributes)));
    notifyClientSuccess(
      "Modèle appliqué",
      `Le modèle "${preset.name}" (${preset.attributes.length} attributs et options) a été chargé.`
    );
  }

  function addColorToRichList() {
    if (!tempColorName.trim()) {
      notifyClientWarning("Nom de couleur manquant", "Veuillez renseigner le nom de la nuance.");
      return;
    }
    const cleanName = tempColorName.trim();
    if (newRichColors.some((c) => c.value.toLowerCase() === cleanName.toLowerCase())) {
      notifyClientWarning("Couleur déjà présente", "Cette nuance figure déjà dans la liste.");
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
        "Champs d'attribut incomplets",
        "Veuillez renseigner la clé technique (ex: fit) et le libellé en français."
      );
      return;
    }
    if (attributes.some((a) => a.attr_key === cleanKey)) {
      notifyClientWarning(
        "Clé d'attribut déjà présente",
        `L'attribut "${cleanKey}" figure déjà dans cette catégorie.`
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
        is_required: newRequired,
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

    notifyClientSuccess("Attribut ajouté", `L'attribut "${newLabelFr.trim()}" a été ajouté au modèle.`);
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
        "Informations incomplètes",
        "Veuillez renseigner au moins le nom français et l'identifiant URL (slug)."
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
          is_required: Boolean(attr.is_required),
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

      const created = await DesktopCmsApi.createCategory(payload);

      const okMsg = `Catégorie "${nameFr}" créée avec succès (${formattedAttrs.length} attributs et ses déclinaisons).`;
      setStatusMsg(okMsg);
      notifyClientSuccess("Catégorie publiée", okMsg);

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
                Architecture des Catégories &amp; Modèles de Variantes
              </h1>
              <p className="text-xs text-gray-500 mt-0.5">
                Configurez les catégories, les attributs techniques et les axes de déclinaisons (couleurs avec nuancier, tailles, matières).
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
            <span>{showCreateForm ? "Fermer le configurateur" : "+ Créer une Catégorie"}</span>
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
              <span>Modèles Dynamiques OK</span>
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

      {/* Upgraded Category Creation Form with Presets & Live Storefront Preview */}
      {showCreateForm && (
        <form
          onSubmit={handleSaveCategory}
          className="bg-white p-6 rounded-2xl border-2 border-[#D4AF62] shadow-xl space-y-6 animate-in fade-in duration-200"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-[#D4AF62]/30 pb-3">
            <div>
              <h2 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
                <SlidersHorizontal className="w-5 h-5 text-[#D4AF62]" />
                <span>Créer une Catégorie &amp; Définir son Modèle de Déclinaisons</span>
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Configurez les attributs, axes de variantes (couleurs avec nuancier, tailles), filtres boutique et prévisualisez le rendu en direct.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowCreateForm(false)}
              className="p-1 rounded-lg text-gray-400 hover:text-gray-700 transition"
              aria-label="Fermer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* 1. Guided Reusable Presets Toolbar */}
          <div className="p-4 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#063D2E] uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-[#D4AF62]" />
                <span>Modèles Rapides &amp; Préréglages Métier (1 Clic)</span>
              </span>
              <span className="text-[11px] text-gray-500">Cliquez sur un modèle pour préremplir instantanément attributs, couleurs et dimensions</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {CATEGORY_PRESETS.map((preset) => {
                const IconComp = preset.iconName === "shirt" ? Shirt : getCategoryIconComponent(preset.slug, preset.iconName);
                const isSelected = activePresetId === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => applyCategoryPreset(preset)}
                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-bold transition border ${
                      isSelected
                        ? "bg-[#063D2E] text-[#D4AF62] border-[#063D2E] shadow-sm"
                        : "bg-white text-gray-800 border-gray-200 hover:border-[#D4AF62] hover:bg-amber-50/50"
                    }`}
                  >
                    <IconComp className="w-3.5 h-3.5 text-[#D4AF62]" />
                    <span>{preset.name}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 2. Category Identity Inputs */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-[#063D2E] uppercase tracking-wider border-b border-gray-200 pb-1">
              1. Identité &amp; Informations de la Catégorie
            </h3>
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
                          .normalize("NFD")
                          .replace(/[^a-z0-9]+/g, "-")
                          .replace(/^-|-$/g, "")
                      );
                    }
                  }}
                  placeholder="ex: T-shirts & Prêt-à-porter"
                  required
                  className="w-full px-3 py-2 border rounded-xl font-semibold"
                />
              </div>
              <div>
                <label className="block font-bold text-[#063D2E] mb-1">Nom Arabe (AR)</label>
                <input
                  value={nameAr}
                  onChange={(e) => setNameAr(e.target.value)}
                  placeholder="قمصان وملابس فاخرة"
                  dir="rtl"
                  className="w-full px-3 py-2 border rounded-xl"
                />
              </div>
              <div>
                <label className="block font-bold text-[#063D2E] mb-1">Nom Anglais (EN)</label>
                <input
                  value={nameEn}
                  onChange={(e) => setNameEn(e.target.value)}
                  placeholder="T-Shirts & Apparel"
                  className="w-full px-3 py-2 border rounded-xl"
                />
              </div>
              <div>
                <label className="block font-bold text-[#063D2E] mb-1">Identifiant URL (Slug) *</label>
                <input
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  placeholder="t-shirts"
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
                  placeholder="T-shirts d'exception, polos raffinés et créations prêt-à-porter en coton Pima noble."
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

            {/* Visual Media Selectors */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs pt-1">
              <div>
                <label className="block font-bold text-[#063D2E] mb-1">Photo Vignette Catégorie</label>
                <input
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl font-mono text-gray-600"
                  placeholder="/assets/cat_vetements.jpg"
                />
                <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                  {[
                    { label: "Vêtements", url: "/assets/cat_vetements.jpg" },
                    { label: "Chaussures", url: "/assets/cat_chaussures.jpg" },
                    { label: "Sacs", url: "/assets/cat_sacs.jpg" },
                    { label: "Montres", url: "/assets/cat_montres.jpg" },
                    { label: "Beauté", url: "/assets/cat_maquillage.jpg" },
                    { label: "Lunettes", url: "/assets/cat_lunettes.jpg" },
                    { label: "Châles", url: "/assets/cat_chales.jpg" },
                  ].map((img) => (
                    <button
                      key={img.url}
                      type="button"
                      onClick={() => setImageUrl(img.url)}
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold transition border ${
                        imageUrl === img.url ? "bg-[#063D2E] text-[#D4AF62] border-[#063D2E]" : "bg-white text-gray-700 border-gray-200 hover:border-gray-400"
                      }`}
                    >
                      {img.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block font-bold text-[#063D2E] mb-1">Bannière En-tête</label>
                <input
                  value={bannerUrl}
                  onChange={(e) => setBannerUrl(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl font-mono text-gray-600"
                  placeholder="/assets/hero_bag_clean.jpg"
                />
                <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                  {[
                    { label: "Hero Sac Couture", url: "/assets/hero_bag_clean.jpg" },
                    { label: "Enseigne Mus", url: "/assets/mus_luxury_sign.jpg" },
                  ].map((img) => (
                    <button
                      key={img.url}
                      type="button"
                      onClick={() => setBannerUrl(img.url)}
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold transition border ${
                        bannerUrl === img.url ? "bg-[#063D2E] text-[#D4AF62] border-[#063D2E]" : "bg-white text-gray-700 border-gray-200 hover:border-gray-400"
                      }`}
                    >
                      {img.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* 3. Two-Column Layout: Attributes Manager (Left) + Live Category Card Preview (Right) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 pt-2 border-t border-gray-200">
            {/* Left Column: Attributes & Options Builder */}
            <div className="lg:col-span-8 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-[#063D2E] uppercase tracking-wider flex items-center gap-2">
                  <SlidersHorizontal className="w-4 h-4 text-[#D4AF62]" />
                  <span>2. Modèle d'Attributs &amp; Déclinaisons ({attributes.length})</span>
                </h3>
                <span className="text-[11px] text-gray-500">
                  Définissez les couleurs, tailles et caractéristiques héritées par les produits
                </span>
              </div>

              {/* Configured Attributes List */}
              <div className="space-y-2">
                {attributes.map((attr, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-[#F8F6F0] rounded-xl border border-[#D4AF62]/35 space-y-2 hover:border-[#D4AF62] transition"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono font-bold text-[#063D2E] bg-white px-2 py-0.5 rounded border border-gray-200 text-xs">
                          {attr.attr_key}
                        </span>
                        <span className="font-bold text-gray-900 text-xs">{attr.label_fr}</span>
                        <span className="px-2 py-0.5 rounded bg-gray-200/80 text-[10px] font-mono text-gray-700">
                          {attr.input_type}
                        </span>
                        {attr.is_variant_axis && (
                          <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-900 text-[10px] font-bold border border-emerald-300">
                            ⚡ Axe de variante (Stock dédié)
                          </span>
                        )}
                        {attr.is_filterable && (
                          <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-900 text-[10px] font-bold border border-amber-300">
                            Filtre boutique
                          </span>
                        )}
                        {attr.is_required && (
                          <span className="px-2 py-0.5 rounded bg-rose-100 text-rose-900 text-[10px] font-bold border border-rose-200">
                            Requis
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => moveDraftAttribute(idx, "up")}
                          disabled={idx === 0}
                          className="p-1 rounded text-gray-500 hover:text-gray-900 disabled:opacity-25"
                          title="Monter"
                        >
                          <ChevronUp className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => moveDraftAttribute(idx, "down")}
                          disabled={idx === attributes.length - 1}
                          className="p-1 rounded text-gray-500 hover:text-gray-900 disabled:opacity-25"
                          title="Descendre"
                        >
                          <ChevronDown className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => removeDraftAttribute(idx)}
                          className="p-1 rounded text-rose-600 hover:bg-rose-50 transition"
                          title="Supprimer cet attribut"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Rich Options preview */}
                    {attr.rich_options && attr.rich_options.length > 0 ? (
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        {attr.rich_options.map((opt, oIdx) => (
                          <span
                            key={oIdx}
                            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white border border-gray-200 text-[11px] font-medium text-gray-800 shadow-2xs"
                          >
                            <span
                              className="w-3 h-3 rounded-full border border-gray-300 shadow-xs"
                              style={{ backgroundColor: opt.color_hex || "#063D2E" }}
                            />
                            <span>{opt.value}</span>
                          </span>
                        ))}
                      </div>
                    ) : attr.options_csv ? (
                      <div className="flex flex-wrap items-center gap-1 pt-1">
                        {attr.options_csv.split(",").map((v, vIdx) => (
                          <span
                            key={vIdx}
                            className="px-2 py-0.5 rounded-md bg-white border border-gray-200 text-[11px] text-gray-700 font-medium"
                          >
                            {v.trim()}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>

              {/* Sub-Builder to add a custom attribute */}
              <div className="p-4 bg-white rounded-xl border border-[#D4AF62]/40 shadow-sm space-y-3 text-xs">
                <span className="font-bold text-[#063D2E] uppercase tracking-wider block">
                  + Ajouter un attribut sur-mesure au modèle
                </span>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                  <div>
                    <label className="block font-semibold mb-1">Clé technique *</label>
                    <input
                      value={newKey}
                      onChange={(e) => setNewKey(e.target.value)}
                      placeholder="ex: col_type"
                      className="w-full px-2.5 py-1.5 border rounded-lg font-mono"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold mb-1">Libellé (FR) *</label>
                    <input
                      value={newLabelFr}
                      onChange={(e) => setNewLabelFr(e.target.value)}
                      placeholder="ex: Type de Col"
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
                  <div>
                    <label className="block font-semibold mb-1">Unité (optionnelle)</label>
                    <input
                      value={newUnit}
                      onChange={(e) => setNewUnit(e.target.value)}
                      placeholder="ex: cm, ml, g"
                      className="w-full px-2.5 py-1.5 border rounded-lg"
                    />
                  </div>
                </div>

                {/* Color Swatch Builder UI */}
                {(newType === "color" || newKey === "color" || newKey.includes("couleur")) ? (
                  <div className="p-3 bg-amber-50/40 rounded-xl border border-amber-200/60 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-[#063D2E] flex items-center gap-1.5">
                        <Palette className="w-4 h-4 text-[#D4AF62]" />
                        <span>Nuancier Visuel &amp; Pastilles Circulaires</span>
                      </span>
                      <span className="text-[11px] text-gray-500">Ajoutez les teintes avec leur pastille couleur</span>
                    </div>

                    {/* Preconfigured Colors Quick Add Palette */}
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] font-bold text-gray-600 mr-1">Palettes Luxe :</span>
                      {LUXURY_PALETTE.map((pal) => (
                        <button
                          key={pal.name}
                          type="button"
                          onClick={() => {
                            setTempColorName(pal.name);
                            setTempColorHex(pal.hex);
                          }}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white border border-gray-200 text-[10px] font-medium hover:border-[#D4AF62] transition"
                        >
                          <span className="w-2.5 h-2.5 rounded-full border border-gray-300" style={{ backgroundColor: pal.hex }} />
                          <span>{pal.name}</span>
                        </button>
                      ))}
                    </div>

                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <div className="flex items-center gap-1.5 bg-white px-2 py-1 border rounded-lg">
                        <input
                          type="color"
                          value={tempColorHex}
                          onChange={(e) => setTempColorHex(e.target.value)}
                          className="w-6 h-6 rounded cursor-pointer border-0 p-0"
                        />
                        <input
                          value={tempColorHex}
                          onChange={(e) => setTempColorHex(e.target.value)}
                          className="w-16 font-mono text-[11px] outline-none"
                          placeholder="#063D2E"
                        />
                      </div>
                      <input
                        value={tempColorName}
                        onChange={(e) => setTempColorName(e.target.value)}
                        placeholder="Nom de la couleur (ex: Vert Émeraude)"
                        className="flex-1 px-2.5 py-1.5 border rounded-lg bg-white"
                      />
                      <button
                        type="button"
                        onClick={addColorToRichList}
                        className="px-3 py-1.5 bg-[#063D2E] text-[#D4AF62] font-bold rounded-lg hover:brightness-110 transition"
                      >
                        + Ajouter cette nuance
                      </button>
                    </div>

                    {/* Current Swatches in Draft */}
                    {newRichColors.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        {newRichColors.map((col) => (
                          <span
                            key={col.value}
                            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white border border-gray-300 text-[11px] font-bold shadow-2xs"
                          >
                            <span className="w-3.5 h-3.5 rounded-full border border-gray-400" style={{ backgroundColor: col.color_hex }} />
                            <span>{col.value}</span>
                            <button
                              type="button"
                              onClick={() => removeColorFromRichList(col.value)}
                              className="text-gray-400 hover:text-red-600 transition"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block font-semibold">Options prédéfinies (séparées par virgule)</label>
                      {(newType === "size" || newKey === "size" || newKey.includes("taille") || newKey.includes("pointure")) && (
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => setNewOptionsCsv("XS, S, M, L, XL, XXL")}
                            className="text-[10px] text-[#063D2E] font-bold hover:underline"
                          >
                            + Tailles Vêtements
                          </button>
                          <span className="text-gray-300">·</span>
                          <button
                            type="button"
                            onClick={() => setNewOptionsCsv("36, 37, 38, 39, 40, 41, 42, 43, 44")}
                            className="text-[10px] text-[#063D2E] font-bold hover:underline"
                          >
                            + Pointures Souliers
                          </button>
                        </div>
                      )}
                    </div>
                    <input
                      value={newOptionsCsv}
                      onChange={(e) => setNewOptionsCsv(e.target.value)}
                      placeholder="ex: Col Rond, Col V, Col Montant"
                      className="w-full px-2.5 py-1.5 border rounded-lg"
                    />
                  </div>
                )}

                {/* Toggles */}
                <div className="flex flex-wrap gap-4 pt-1">
                  <label className="inline-flex items-center gap-1.5 cursor-pointer font-semibold text-[#063D2E]">
                    <input
                      type="checkbox"
                      checked={newVariantAxis}
                      onChange={(e) => setNewVariantAxis(e.target.checked)}
                      className="rounded text-[#063D2E]"
                    />
                    <span>⚡ Axe de variante (génère stocks &amp; déclinaisons)</span>
                  </label>
                  <label className="inline-flex items-center gap-1.5 cursor-pointer font-semibold">
                    <input
                      type="checkbox"
                      checked={newFilterable}
                      onChange={(e) => setNewFilterable(e.target.checked)}
                      className="rounded text-[#063D2E]"
                    />
                    <span>Filtrable sur la boutique</span>
                  </label>
                  <label className="inline-flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newVisibleOnStorefront}
                      onChange={(e) => setNewVisibleOnStorefront(e.target.checked)}
                      className="rounded text-[#063D2E]"
                    />
                    <span>Visible sur fiche article</span>
                  </label>
                  <label className="inline-flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newRequired}
                      onChange={(e) => setNewRequired(e.target.checked)}
                      className="rounded text-[#063D2E]"
                    />
                    <span>Obligatoire</span>
                  </label>
                </div>

                <div className="flex justify-end pt-1">
                  <button
                    type="button"
                    onClick={addDraftAttribute}
                    className="px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold hover:bg-[#02291F] transition flex items-center gap-1.5"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Ajouter cet attribut au modèle</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Right Column: Live Storefront Category Card & Attributes Preview */}
            <div className="lg:col-span-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#063D2E] uppercase tracking-wider flex items-center gap-1.5">
                  <Eye className="w-4 h-4 text-[#D4AF62]" />
                  <span>Aperçu Vitrine en Direct</span>
                </span>
                <span className="text-[10px] font-bold text-[#D4AF62] bg-[#063D2E] px-2 py-0.5 rounded-full">
                  Live Preview
                </span>
              </div>

              {/* Card Container */}
              <div className="rounded-2xl border-2 border-[#D4AF62]/50 bg-[#063D2E] text-white p-4 shadow-xl space-y-3 overflow-hidden relative">
                {/* Image Banner */}
                <div className="relative h-32 rounded-xl overflow-hidden bg-black/40 border border-white/10">
                  <img
                    src={imageUrl || "/assets/cat_vetements.jpg"}
                    alt={nameFr || "Catégorie"}
                    className="w-full h-full object-cover object-center"
                    onError={(e: any) => {
                      e.target.src = "/assets/hero_bag_clean.jpg";
                    }}
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#063D2E] via-transparent to-black/20" />
                  <span className="absolute bottom-2 left-2 text-[10px] font-mono tracking-widest text-[#D4AF62] uppercase bg-black/60 px-2 py-0.5 rounded-full backdrop-blur-xs">
                    /{slug || "slug-url"}
                  </span>
                </div>

                {/* Identity */}
                <div>
                  <h4 className="font-serif text-lg font-bold text-[#D4AF62]">
                    {nameFr || "T-shirts & Prêt-à-porter"}
                  </h4>
                  {nameAr && <p className="text-xs text-amber-100/70" dir="rtl">{nameAr}</p>}
                  <p className="text-xs text-gray-200/90 mt-1 line-clamp-2">
                    {descriptionFr || "Description de la collection d'exception..."}
                  </p>
                </div>

                {/* Variant Dimensions Preview */}
                <div className="pt-2 border-t border-white/15 space-y-2 text-xs">
                  <span className="text-[11px] font-bold text-[#D4AF62] uppercase tracking-wider block">
                    Déclinaisons &amp; Sélecteurs Fiche Produit :
                  </span>

                  {attributes.filter((a) => a.is_variant_axis).length === 0 ? (
                    <span className="text-[11px] text-gray-300 italic">Aucun axe de déclinaison configuré</span>
                  ) : (
                    attributes
                      .filter((a) => a.is_variant_axis)
                      .map((axis, aIdx) => (
                        <div key={aIdx} className="space-y-1">
                          <span className="text-[11px] text-gray-300 font-semibold">{axis.label_fr} :</span>
                          {axis.input_type === "color" && axis.rich_options ? (
                            <div className="flex flex-wrap items-center gap-1.5">
                              {axis.rich_options.map((opt, oIdx) => (
                                <span
                                  key={oIdx}
                                  className="w-4 h-4 rounded-full border border-white/40 shadow-xs inline-block"
                                  style={{ backgroundColor: opt.color_hex || "#FFFFFF" }}
                                  title={opt.label_fr || opt.value}
                                />
                              ))}
                            </div>
                          ) : (
                            <div className="flex flex-wrap items-center gap-1">
                              {(axis.rich_options || axis.options_csv.split(",").map((v) => ({ value: v.trim() })))
                                .slice(0, 6)
                                .map((opt, oIdx) => (
                                  <span
                                    key={oIdx}
                                    className="px-1.5 py-0.5 rounded bg-white/15 text-[9px] font-bold text-white border border-white/20"
                                  >
                                    {opt.value}
                                  </span>
                                ))}
                            </div>
                          )}
                        </div>
                      ))
                  )}
                </div>

                {/* Filters preview */}
                <div className="pt-2 border-t border-white/15 text-[10px]">
                  <span className="font-bold text-amber-200/80 uppercase block mb-1">
                    Filtres Boutique ({attributes.filter((a) => a.is_filterable).length}) :
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {attributes
                      .filter((a) => a.is_filterable)
                      .map((a, fIdx) => (
                        <span key={fIdx} className="px-1.5 py-0.5 rounded bg-black/40 text-amber-200 border border-white/10">
                          {a.label_fr}
                        </span>
                      ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Form Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#D4AF62]/30">
            <button
              type="button"
              onClick={() => setShowCreateForm(false)}
              className="px-4 py-2.5 rounded-xl border border-gray-300 font-bold text-gray-700 text-xs hover:bg-gray-50 transition"
            >
              Annuler
            </button>
            <button
              type="submit"
              className="px-6 py-2.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-xs shadow-md hover:brightness-105 transition flex items-center gap-2"
            >
              <Check className="w-4 h-4" />
              <span>Enregistrer &amp; Publier la Catégorie</span>
            </button>
          </div>
        </form>
      )}
'''

full_file = header_and_presets + component_code + '\n\n      ' + table_and_modals_jsx

with open('apps/desktop-cms/src/pages/CategoryBuilderPage.tsx', 'w', encoding='utf-8') as f:
    f.write(full_file)

print(f"Generated CategoryBuilderPage.tsx successfully: {len(full_file)} characters.")
