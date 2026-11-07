import os

filepath = 'apps/desktop-cms/src/components/VariantManager.tsx'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add removeCustomValue right after addCustomValue
target_add = '''    const axis = axes.find((a) => a.attr_key === axisKey);
    if (axis && axis.id) {
      DesktopCmsApi.createAttributeOption(axis.id, {
        value,
        label_fr: value,
        color_hex: hex || undefined,
      }).catch(() => null);
    }
  }'''

replacement_add = '''    const axis = axes.find((a) => a.attr_key === axisKey);
    if (axis && axis.id) {
      DesktopCmsApi.createAttributeOption(axis.id, {
        value,
        label_fr: value,
        color_hex: hex || undefined,
      }).catch(() => null);
    }
  }

  function removeCustomValue(axisKey: string, value: string) {
    setSelection((prev) => ({
      ...prev,
      [axisKey]: (prev[axisKey] || []).filter((v) => v !== value),
    }));
    setCustomMeta((prev) => {
      const copy = { ...prev };
      delete copy[`${axisKey}:${value}`];
      return copy;
    });
  }'''

if target_add not in content:
    raise Exception("target_add not found in VariantManager.tsx")
content = content.replace(target_add, replacement_add)

# 2. Replace the custom values rendering and color input box
target_ui = '''              {(selection[axis.attr_key] || [])
                .filter((v) => !(axis.options || []).some((o) => o.value === v))
                .map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => toggleValue(axis.attr_key, v)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border font-semibold bg-amber-50 text-amber-900 border-amber-300"
                    title="Valeur personnalisée (sera ajoutée à la bibliothèque d'options)"
                  >
                    <span>{v}</span>
                    <X className="w-3 h-3" />
                  </button>
                ))}
              {axis.input_type === "color" || axis.attr_key.toLowerCase().includes("color") || axis.attr_key.toLowerCase().includes("couleur") ? (
                <div className="flex items-center gap-1.5 p-1 rounded-xl bg-white border border-[#D4AF62]/40 shadow-xs">
                  <input
                    type="color"
                    value={customColorHex[axis.attr_key] || "#063D2E"}
                    onChange={(e) => setCustomColorHex((p) => ({ ...p, [axis.attr_key]: e.target.value }))}
                    className="w-6 h-6 rounded cursor-pointer border-0 p-0 bg-transparent"
                    title="Choisir une nuance sur la palette"
                  />
                  <input
                    value={customColorHex[axis.attr_key] || "#063D2E"}
                    onChange={(e) => setCustomColorHex((p) => ({ ...p, [axis.attr_key]: e.target.value }))}
                    placeholder="#HEX"
                    className="w-16 px-1 py-0.5 font-mono uppercase text-[10px] border rounded bg-white text-center"
                  />
                  <input
                    value={customValue[axis.attr_key] || ""}
                    onChange={(e) => setCustomValue((p) => ({ ...p, [axis.attr_key]: e.target.value }))}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addCustomValue(axis.attr_key, customColorHex[axis.attr_key] || "#063D2E");
                      }
                    }}
                    placeholder="Nom (ex: Vert sauge)…"
                    className="w-28 px-2 py-1 border rounded-lg bg-white text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => addCustomValue(axis.attr_key, customColorHex[axis.attr_key] || "#063D2E")}
                    className="px-2 py-1 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold hover:brightness-110 shadow-xs"
                    title="Créer cette couleur visuelle"
                  >
                    <Plus className="w-3 h-3" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-1">
                  <input
                    value={customValue[axis.attr_key] || ""}
                    onChange={(e) => setCustomValue((p) => ({ ...p, [axis.attr_key]: e.target.value }))}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addCustomValue(axis.attr_key);
                      }
                    }}
                    placeholder="Autre valeur…"
                    className="w-28 px-2 py-1 border border-dashed rounded-lg bg-white text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => addCustomValue(axis.attr_key)}
                    className="px-2 py-1 rounded-lg bg-white border border-[#D4AF62] font-bold text-[#063D2E]"
                    title="Ajouter cette valeur personnalisée"
                  >
                    <Plus className="w-3 h-3" />
                  </button>
                </div>
              )}'''

replacement_ui = '''              {/* Custom values styled exactly like suggested options */}
              {(selection[axis.attr_key] || [])
                .filter((v) => !(axis.options || []).some((o) => o.value === v))
                .map((v) => {
                  const isColor = axis.input_type === "color" || axis.attr_key.toLowerCase().includes("color") || axis.attr_key.toLowerCase().includes("couleur");
                  const hex = customMeta[`${axis.attr_key}:${v}`]?.color_hex || customColorHex[axis.attr_key] || "#063D2E";
                  const active = (selection[axis.attr_key] || []).includes(v);
                  return (
                    <div key={v} className="inline-flex items-center group">
                      <button
                        type="button"
                        onClick={() => toggleValue(axis.attr_key, v)}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-l-lg border font-semibold transition ${
                          active
                            ? "bg-[#063D2E] text-[#E8D4A5] border-[#063D2E] shadow-xs"
                            : "bg-white text-gray-700 border-gray-300 hover:border-[#063D2E]"
                        }`}
                      >
                        {isColor && (
                          <span
                            className="w-3 h-3 rounded-full border border-white/60 shadow-xs flex-shrink-0"
                            style={{ backgroundColor: hex }}
                          />
                        )}
                        <span>{v}</span>
                        {active && <Check className="w-3 h-3 text-[#D4AF62]" />}
                      </button>
                      <button
                        type="button"
                        onClick={() => removeCustomValue(axis.attr_key, v)}
                        className={`px-1.5 py-1 rounded-r-lg border border-l-0 text-xs transition ${
                          active
                            ? "bg-[#063D2E] text-[#E8D4A5]/70 hover:text-red-300 border-[#063D2E]"
                            : "bg-white text-gray-400 hover:text-red-500 border-gray-300"
                        }`}
                        title="Retirer cette option personnalisée"
                      >
                        <X className="w-2.5 h-2.5" />
                      </button>
                    </div>
                  );
                })}

              {/* Add Custom Value with live color circle beside name */}
              {axis.input_type === "color" || axis.attr_key.toLowerCase().includes("color") || axis.attr_key.toLowerCase().includes("couleur") ? (
                <div className="flex items-center gap-2 p-1.5 rounded-xl bg-white border border-[#D4AF62]/40 shadow-xs">
                  <div className="flex items-center gap-1.5 bg-gray-50 px-1.5 py-0.5 rounded-lg border border-gray-200">
                    <input
                      type="color"
                      value={customColorHex[axis.attr_key] || "#063D2E"}
                      onChange={(e) => setCustomColorHex((p) => ({ ...p, [axis.attr_key]: e.target.value }))}
                      className="w-6 h-6 rounded cursor-pointer border-0 p-0 bg-transparent"
                      title="Choisir une nuance sur la palette"
                    />
                    <input
                      value={customColorHex[axis.attr_key] || "#063D2E"}
                      onChange={(e) => setCustomColorHex((p) => ({ ...p, [axis.attr_key]: e.target.value }))}
                      placeholder="#HEX"
                      className="w-16 px-1 py-0.5 font-mono uppercase text-[10px] border-0 bg-transparent text-center font-bold text-gray-700 outline-none"
                    />
                  </div>
                  {/* Live circular color swatch beside the name input */}
                  <span
                    className="w-4 h-4 rounded-full border border-gray-300 shadow-xs flex-shrink-0 transition-transform duration-200"
                    style={{ backgroundColor: customColorHex[axis.attr_key] || "#063D2E" }}
                    title={customColorHex[axis.attr_key] || "#063D2E"}
                  />
                  <input
                    value={customValue[axis.attr_key] || ""}
                    onChange={(e) => setCustomValue((p) => ({ ...p, [axis.attr_key]: e.target.value }))}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addCustomValue(axis.attr_key, customColorHex[axis.attr_key] || "#063D2E");
                      }
                    }}
                    placeholder="Nom de la couleur (ex: Vert sauge)…"
                    className="w-36 sm:w-44 px-2 py-1 border rounded-lg bg-white text-xs font-medium"
                  />
                  <button
                    type="button"
                    onClick={() => addCustomValue(axis.attr_key, customColorHex[axis.attr_key] || "#063D2E")}
                    className="px-2.5 py-1.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold hover:brightness-110 shadow-xs flex items-center gap-1 text-xs"
                    title="Ajouter cette couleur"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 p-1 rounded-xl bg-white border border-gray-300">
                  <input
                    value={customValue[axis.attr_key] || ""}
                    onChange={(e) => setCustomValue((p) => ({ ...p, [axis.attr_key]: e.target.value }))}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addCustomValue(axis.attr_key);
                      }
                    }}
                    placeholder={`Autre ${axis.label_fr}…`}
                    className="w-32 px-2 py-1 border rounded-lg bg-white text-xs font-medium"
                  />
                  <button
                    type="button"
                    onClick={() => addCustomValue(axis.attr_key)}
                    className="px-2.5 py-1 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold text-xs flex items-center gap-1 shadow-xs"
                    title="Ajouter cette option"
                  >
                    <Plus className="w-3 h-3" />
                  </button>
                </div>
              )}'''

if target_ui not in content:
    raise Exception("target_ui not found in VariantManager.tsx")
content = content.replace(target_ui, replacement_ui)

# 3. In the combination table, look up custom color hex in customMeta
target_badge = 'const hex = badgeColor(val, axis);'
replacement_badge = 'const hex = customMeta[`${axis.attr_key}:${val}`]?.color_hex || badgeColor(val, axis);'

if target_badge not in content:
    raise Exception("target_badge not found in VariantManager.tsx")
content = content.replace(target_badge, replacement_badge)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully patched VariantManager.tsx with live color circles and suggested-style pills!")

