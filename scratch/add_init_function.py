with open('scratch/generate_upgraded_category_page.py', 'r', encoding='utf-8') as f:
    text = f.read()

func = '''  async function handleInitializeLuxuryStarterCollections() {
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

'''

text = text.replace('  async function loadCategories() {', func + '  async function loadCategories() {')
with open('scratch/generate_upgraded_category_page.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated generate_upgraded_category_page.py with handleInitializeLuxuryStarterCollections.')
