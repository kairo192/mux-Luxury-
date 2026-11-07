import os

# Read the original file to get everything from line 1098 onwards
with open('apps/desktop-cms/src/pages/CategoryBuilderPage.tsx', 'r', encoding='utf-8') as f:
    orig = f.read()

cut_toolbar = '{/* Categories Toolbar: Search & Filters */}'
if cut_toolbar not in orig:
    raise Exception("cut_toolbar not found!")

table_and_modals_jsx = cut_toolbar + orig.split(cut_toolbar)[1]

# Also extract the existing edit modal functions and delete functions between handleSaveCategory and showCreateForm
cut_edit_start = '  // Open Edit Modal\n  function handleOpenEdit(cat: any) {'
cut_render_start = '  return (\n    <div className="space-y-6 pb-12">'

if cut_edit_start not in orig or cut_render_start not in orig:
    raise Exception("Edit or Render markers not found!")

edit_and_helpers = cut_edit_start + orig.split(cut_edit_start)[1].split(cut_render_start)[0]

# Now let's build the full enhanced JSX for the form:
form_jsx = '''      {/* Collapsible Category Creation Form with Presets & Live Preview */}
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
                Configurez les attributs, axes de variantes (couleurs, tailles), filtres boutique et prévisualisez le rendu en direct.
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
              <span className="text-[11px] text-gray-500">Cliquez sur un modèle pour préremplir instantanément attributs et options</span>
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

          {/* 2. Category Metadata Inputs */}
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

            {/* Image & Banner Selectors */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs pt-1">
              <div className="p-3 rounded-xl bg-gray-50 border border-gray-200 space-y-2">
                <label className="block font-bold text-[#063D2E]">Image Vignette Catégorie</label>
                <input
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                  placeholder="/assets/cat_sacs.jpg"
                  className="w-full px-3 py-1.5 border rounded-lg font-mono text-[11px] bg-white"
                />
                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="text-[10px] text-gray-500 font-semibold">Images disponibles :</span>
                  {STANDARD_ASSET_IMAGES.slice(0, 5).map((img) => (
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

              <div className="p-3 rounded-xl bg-gray-50 border border-gray-200 space-y-2">
                <label className="block font-bold text-[#063D2E]">Bannière d'En-tête (Optionnel)</label>
                <input
                  value={bannerUrl}
                  onChange={(e) => setBannerUrl(e.target.value)}
                  placeholder="/assets/hero_bag_clean.jpg"
                  className="w-full px-3 py-1.5 border rounded-lg font-mono text-[11px] bg-white"
                />
                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="text-[10px] text-gray-500 font-semibold">Bannières :</span>
                  {STANDARD_ASSET_IMAGES.slice(5).map((img) => (
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
                            🔍 Filtre boutique
                          </span>
                        )}
                        {attr.is_required && (
                          <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-900 text-[10px] font-bold border border-blue-300">
                            📌 Obligatoire
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => moveAttributeUp(idx)}
                          disabled={idx === 0}
                          className="p-1 rounded bg-white hover:bg-gray-100 disabled:opacity-30 border text-gray-600"
                          title="Monter"
                        >
                          <ArrowUp className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => moveAttributeDown(idx)}
                          disabled={idx === attributes.length - 1}
                          className="p-1 rounded bg-white hover:bg-gray-100 disabled:opacity-30 border text-gray-600"
                          title="Descendre"
                        >
                          <ArrowDown className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => removeDraftAttribute(idx)}
                          className="p-1 rounded bg-white hover:bg-red-50 text-red-600 border border-red-200 hover:border-red-400 font-bold ml-1"
                          title="Supprimer cet attribut"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Rich Options / Swatches preview */}
                    {attr.rich_options && attr.rich_options.length > 0 ? (
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        {attr.rich_options.map((opt, oIdx) => (
                          <div
                            key={oIdx}
                            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-white border border-gray-200 text-xs shadow-xs"
                          >
                            {opt.color_hex && (
                              <span
                                className="w-3.5 h-3.5 rounded-full border border-black/25 flex-shrink-0"
                                style={{ backgroundColor: opt.color_hex }}
                              />
                            )}
                            <span className="font-medium text-gray-800">{opt.label_fr || opt.value}</span>
                            {opt.color_hex && (
                              <span className="font-mono text-[9px] text-gray-400">{opt.color_hex}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : attr.options_csv ? (
                      <p className="text-[11px] text-gray-600 font-mono bg-white p-1.5 rounded border border-gray-200 truncate">
                        Options : [{attr.options_csv}]
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>

              {/* Add New Attribute Box */}
              <div className="p-4 rounded-xl bg-white border-2 border-dashed border-[#D4AF62]/50 space-y-3 text-xs">
                <span className="font-bold text-[#063D2E] block uppercase tracking-wider">
                  + Ajouter un Attribut Personnalisé au Modèle
                </span>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                  <div>
                    <label className="block font-semibold mb-1 text-gray-700">Code technique</label>
                    <input
                      value={newKey}
                      onChange={(e) => setNewKey(e.target.value)}
                      placeholder="ex: coupe"
                      className="w-full px-2.5 py-1.5 border rounded-lg font-mono bg-gray-50 focus:bg-white"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold mb-1 text-gray-700">Libellé (FR)</label>
                    <input
                      value={newLabelFr}
                      onChange={(e) => setNewLabelFr(e.target.value)}
                      placeholder="ex: Coupe du vêtement"
                      className="w-full px-2.5 py-1.5 border rounded-lg bg-gray-50 focus:bg-white"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold mb-1 text-gray-700">Type de champ</label>
                    <select
                      value={newType}
                      onChange={(e) => {
                        setNewType(e.target.value);
                        setRichOptionsDraft([]);
                      }}
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
                    <label className="block font-semibold mb-1 text-gray-700">Unité (ex: cm, g, ml)</label>
                    <input
                      value={newUnit}
                      onChange={(e) => setNewUnit(e.target.value)}
                      placeholder="cm"
                      className="w-full px-2.5 py-1.5 border rounded-lg bg-gray-50 focus:bg-white font-mono"
                    />
                  </div>
                </div>

                {/* Toggles */}
                <div className="flex flex-wrap items-center gap-4 py-1 text-xs text-gray-700">
                  <label className="inline-flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newVariantAxis}
                      onChange={(e) => setNewVariantAxis(e.target.checked)}
                      className="rounded text-[#063D2E]"
                    />
                    <span className="font-bold text-[#063D2E]">Axe de variante (génère stock et prix dédiés)</span>
                  </label>
                  <label className="inline-flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newFilterable}
                      onChange={(e) => setNewFilterable(e.target.checked)}
                      className="rounded text-amber-700"
                    />
                    <span>Afficher dans les filtres boutique</span>
                  </label>
                  <label className="inline-flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newRequired}
                      onChange={(e) => setNewRequired(e.target.checked)}
                      className="rounded text-blue-700"
                    />
                    <span>Champ obligatoire</span>
                  </label>
                </div>

                {/* Specialized Options Editors depending on input_type */}
                {newType === "color" && (
                  <div className="p-3 rounded-xl bg-amber-50/50 border border-[#D4AF62]/40 space-y-2">
                    <span className="font-bold text-[#063D2E] block text-[11px] uppercase tracking-wider flex items-center gap-1.5">
                      <Palette className="w-3.5 h-3.5 text-[#D4AF62]" />
                      <span>Palette de Nuances de Couleur Visuelles</span>
                    </span>

                    {/* Quick Palette Chips */}
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] text-gray-500 font-semibold">Nuances standards :</span>
                      {LUXURY_PALETTE.map((pal) => (
                        <button
                          key={pal.name}
                          type="button"
                          onClick={() => addDraftColorOption(pal.name, pal.hex)}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white border border-gray-300 hover:border-[#D4AF62] text-[11px] font-medium transition"
                        >
                          <span className="w-3 h-3 rounded-full border border-black/20" style={{ backgroundColor: pal.hex }} />
                          <span>{pal.name}</span>
                        </button>
                      ))}
                    </div>

                    {/* Custom Color Input with Native Picker */}
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-white border border-gray-300">
                        <input
                          type="color"
                          value={newColorHex}
                          onChange={(e) => setNewColorHex(e.target.value)}
                          className="w-6 h-6 rounded cursor-pointer border-0 p-0 bg-transparent"
                          title="Choisir couleur"
                        />
                        <input
                          value={newColorHex}
                          onChange={(e) => setNewColorHex(e.target.value)}
                          placeholder="#HEX"
                          className="w-16 font-mono uppercase text-[10px] border-0 p-0 bg-transparent text-center font-bold"
                        />
                      </div>
                      <input
                        value={newColorName}
                        onChange={(e) => setNewColorName(e.target.value)}
                        placeholder="Nom nuance (ex: Vert Sauge)…"
                        className="px-2.5 py-1.5 border rounded-lg bg-white flex-1 min-w-[140px]"
                      />
                      <button
                        type="button"
                        onClick={() => addDraftColorOption()}
                        className="px-3 py-1.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold text-xs shadow-xs hover:brightness-110"
                      >
                        + Ajouter cette nuance
                      </button>
                    </div>

                    {/* Current Draft Colors */}
                    {richOptionsDraft.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        <span className="text-[10px] text-gray-500 font-semibold">Nuances configurées ({richOptionsDraft.length}) :</span>
                        {richOptionsDraft.map((opt) => (
                          <span
                            key={opt.value}
                            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-white border border-gray-300 text-xs font-semibold"
                          >
                            <span className="w-3 h-3 rounded-full border border-black/20" style={{ backgroundColor: opt.color_hex || "#000" }} />
                            <span>{opt.value}</span>
                            <button
                              type="button"
                              onClick={() => removeRichOption(opt.value)}
                              className="text-gray-400 hover:text-red-600 ml-0.5"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {newType === "size" && (
                  <div className="p-3 rounded-xl bg-blue-50/50 border border-blue-200 space-y-2">
                    <span className="font-bold text-[#063D2E] block text-[11px] uppercase tracking-wider">
                      Grilles de Tailles &amp; Pointures
                    </span>

                    {/* Standard Groups */}
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] text-gray-500 font-semibold">Grilles pré-définies :</span>
                      <button
                        type="button"
                        onClick={() => applySizeGroupPreset(["XS", "S", "M", "L", "XL", "XXL", "3XL"])}
                        className="px-2 py-0.5 rounded bg-white border border-blue-300 hover:border-blue-500 text-[10px] font-bold text-blue-900"
                      >
                        Vêtements (XS à 3XL)
                      </button>
                      <button
                        type="button"
                        onClick={() => applySizeGroupPreset(["36", "37", "38", "39", "40", "41"])}
                        className="px-2 py-0.5 rounded bg-white border border-blue-300 hover:border-blue-500 text-[10px] font-bold text-blue-900"
                      >
                        Pointures Femme (36 à 41)
                      </button>
                      <button
                        type="button"
                        onClick={() => applySizeGroupPreset(["39", "40", "41", "42", "43", "44", "45"])}
                        className="px-2 py-0.5 rounded bg-white border border-blue-300 hover:border-blue-500 text-[10px] font-bold text-blue-900"
                      >
                        Pointures Homme (39 à 45)
                      </button>
                      <button
                        type="button"
                        onClick={() => applySizeGroupPreset(["Mini", "Petit", "Standard", "Grand", "Cabas"])}
                        className="px-2 py-0.5 rounded bg-white border border-blue-300 hover:border-blue-500 text-[10px] font-bold text-blue-900"
                      >
                        Formats Maroquinerie
                      </button>
                    </div>

                    {/* Custom Size Input */}
                    <div className="flex items-center gap-2 pt-1">
                      <input
                        value={newSizeValue}
                        onChange={(e) => setNewSizeValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            addDraftSizeOption();
                          }
                        }}
                        placeholder="Ajouter une taille ou pointure personnalisée (ex: 4XL ou 38.5)…"
                        className="px-2.5 py-1.5 border rounded-lg bg-white flex-1"
                      />
                      <button
                        type="button"
                        onClick={() => addDraftSizeOption()}
                        className="px-3 py-1.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold text-xs"
                      >
                        + Ajouter taille
                      </button>
                    </div>

                    {/* Current Draft Sizes */}
                    {richOptionsDraft.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        <span className="text-[10px] text-gray-500 font-semibold">Tailles configurées ({richOptionsDraft.length}) :</span>
                        {richOptionsDraft.map((opt) => (
                          <span
                            key={opt.value}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white border border-gray-300 text-xs font-bold text-gray-800"
                          >
                            <span>{opt.value}</span>
                            <button
                              type="button"
                              onClick={() => removeRichOption(opt.value)}
                              className="text-gray-400 hover:text-red-600 ml-0.5"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {newType !== "color" && newType !== "size" && (
                  <div>
                    <label className="block font-semibold mb-1 text-gray-700">Options (séparées par des virgules)</label>
                    <input
                      value={newOptionsCsv}
                      onChange={(e) => setNewOptionsCsv(e.target.value)}
                      placeholder="ex: Coupe Droite, Coupe Slim, Coupe Oversize"
                      className="w-full px-2.5 py-1.5 border rounded-lg bg-white"
                    />
                  </div>
                )}

                <div className="flex justify-end pt-1">
                  <button
                    type="button"
                    onClick={addDraftAttribute}
                    className="px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-xs shadow-sm hover:brightness-110 flex items-center gap-1.5"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Ajouter cet attribut au modèle</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Right Column: Interactive Live Category Card Preview */}
            <div className="lg:col-span-4 space-y-3">
              <span className="text-xs font-bold text-[#063D2E] uppercase tracking-wider block">
                3. Prévisualisation Boutique en Direct
              </span>

              <div className="rounded-2xl border-2 border-[#D4AF62] bg-[#063D2E] text-white overflow-hidden shadow-xl space-y-3 p-4">
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded-full bg-[#D4AF62]/20 border border-[#D4AF62]/40 text-[#D4AF62] text-[10px] font-bold uppercase tracking-wider">
                    Aperçu Storefront
                  </span>
                  <span className="text-[10px] text-white/60 font-mono">slug: {slug || "t-shirts"}</span>
                </div>

                <div className="relative aspect-[4/3] rounded-xl overflow-hidden border border-[#D4AF62]/30 bg-[#02291F]">
                  <img
                    src={imageUrl || "/assets/cat_sacs.jpg"}
                    alt="Aperçu Catégorie"
                    className="w-full h-full object-cover"
                    onError={(e: any) => { e.target.src = "/assets/cat_sacs.jpg"; }}
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#02291F]/90 via-transparent to-transparent" />
                  <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between text-xs">
                    <span className="font-bold text-white truncate">{nameFr || "Nom de la Catégorie"}</span>
                    <span className="w-2 h-2 rounded-full bg-[#D4AF62] animate-pulse" />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <h4 className="font-serif font-bold text-[#D4AF62] text-sm truncate">{nameFr || "Nouvelle Catégorie"}</h4>
                    {nameAr && <span className="text-xs text-white/80 font-medium" dir="rtl">{nameAr}</span>}
                  </div>
                  <p className="text-[11px] text-white/70 line-clamp-2 leading-relaxed">
                    {descriptionFr || "La description configurée apparaîtra dans les bannières de filtres et sur la page boutique."}
                  </p>
                </div>

                {/* Live Variant Axes Mock */}
                <div className="pt-2 border-t border-white/10 space-y-2">
                  <span className="text-[10px] uppercase tracking-wider text-[#D4AF62] font-bold block">
                    Axes de déclinaison générés :
                  </span>

                  {attributes.filter((a) => a.is_variant_axis).length === 0 ? (
                    <p className="text-[10px] text-white/50 italic">Aucun axe de variante défini pour le moment.</p>
                  ) : (
                    attributes
                      .filter((a) => a.is_variant_axis)
                      .map((axis, aIdx) => (
                        <div key={aIdx} className="space-y-1">
                          <span className="text-[10px] text-white/80 font-semibold">{axis.label_fr} :</span>
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

# Assemble the whole file
new_full_content = script_content + edit_and_helpers + cut_render_start + '\n' + form_jsx + '\n\n      ' + table_and_modals_jsx

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_full_content)

print(f"Successfully assembled full CategoryBuilderPage.tsx ({len(new_full_content)} characters).")
