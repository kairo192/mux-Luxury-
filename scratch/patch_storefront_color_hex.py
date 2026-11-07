filepath = 'apps/storefront/index.html'
with open(filepath, 'r', encoding='utf-8') as f:
    c = f.read()

old_attr_map = '''            attributes: (c.attributes || []).map((a) => ({
              key: a.attr_key,
              label_fr: a.label_fr,
              label_ar: a.label_ar || a.label_fr,
              label_en: a.label_en || a.label_fr,
              type: a.input_type,
              variant: Boolean(a.is_variant_axis),
              filterable: Boolean(a.is_filterable),
              options: (a.options || []).map((o) => o.value),
            })),'''

new_attr_map = '''            attributes: (c.attributes || []).map((a) => {
              (a.options || []).forEach((opt) => {
                if (opt.value && opt.color_hex) {
                  COLOR_SWATCH_HEX[opt.value] = opt.color_hex;
                }
              });
              return {
                key: a.attr_key,
                label_fr: a.label_fr,
                label_ar: a.label_ar || a.label_fr,
                label_en: a.label_en || a.label_fr,
                type: a.input_type,
                variant: Boolean(a.is_variant_axis),
                filterable: Boolean(a.is_filterable),
                options: (a.options || []).map((o) => o.value),
                rawOptions: a.options || [],
              };
            }),'''

c = c.replace(old_attr_map, new_attr_map)

old_swatch_lookup = 'const hex = COLOR_SWATCH_HEX[val] || "#063D2E";'
new_swatch_lookup = 'const hex = COLOR_SWATCH_HEX[val] || (axisAttr.rawOptions && axisAttr.rawOptions.find(o => o.value === val)?.color_hex) || "#063D2E";'
c = c.replace(old_swatch_lookup, new_swatch_lookup)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(c)

print('Updated storefront dynamic color swatch lookup.')

