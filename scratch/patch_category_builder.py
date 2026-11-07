with open('apps/desktop-cms/src/pages/CategoryBuilderPage.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''                      <input
                        value={tempColorName}
                        onChange={(e) => setTempColorName(e.target.value)}
                        placeholder="Nom de la couleur (ex: Vert Émeraude)"
                        className="flex-1 px-2.5 py-1.5 border rounded-lg bg-white"
                      />'''

replacement = '''                      {/* Live circular preview beside name input */}
                      <span
                        className="w-4 h-4 rounded-full border border-gray-300 shadow-xs flex-shrink-0"
                        style={{ backgroundColor: tempColorHex }}
                        title={tempColorHex}
                      />
                      <input
                        value={tempColorName}
                        onChange={(e) => setTempColorName(e.target.value)}
                        placeholder="Nom de la couleur (ex: Vert Émeraude)"
                        className="flex-1 px-2.5 py-1.5 border rounded-lg bg-white text-xs font-medium"
                      />'''

if target not in text:
    raise Exception("target not found in CategoryBuilderPage.tsx")

text = text.replace(target, replacement)

with open('apps/desktop-cms/src/pages/CategoryBuilderPage.tsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("Successfully added live color circle in CategoryBuilderPage.tsx")

