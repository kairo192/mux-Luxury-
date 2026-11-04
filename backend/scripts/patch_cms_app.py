import re

app_path = r"c:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce\apps\desktop-cms\src\App.tsx"

with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 1. Locate the block from <form onSubmit={handleCreateProduct} to the end of {editingProduct && ...}
start_idx = None
end_idx = None

for i, line in enumerate(lines):
    if '<form onSubmit={handleCreateProduct}' in line:
        start_idx = i
        break

assert start_idx is not None, "Could not find start of legacy product form"

for i in range(start_idx, len(lines)):
    if '{/* Product Catalogue Table & Tools */}' in lines[i]:
        end_idx = i
        break

assert end_idx is not None, "Could not find Product Catalogue Table marker"

print(f"Removing legacy forms between lines {start_idx+1} and {end_idx} ({end_idx - start_idx} lines)...")
del lines[start_idx:end_idx]

# 2. Replace onClick={() => setEditingProduct(p)} with onClick={() => openProductEditor(p)}
content = "".join(lines)
assert "onClick={() => setEditingProduct(p)}" in content, "setEditingProduct(p) not found"
content = content.replace("onClick={() => setEditingProduct(p)}", "onClick={() => openProductEditor(p)}")
print("Replaced setEditingProduct(p) with openProductEditor(p).")

# 3. Mount <ProductEditor> before </main>
editor_mount = """      <ProductEditor
        open={productEditorOpen}
        product={productEditorTarget}
        categories={categories}
        brands={brands}
        initialCategoryId={productEditorInitialCat}
        onClose={() => {
          setProductEditorOpen(false);
          setProductEditorTarget(null);
        }}
        onSaved={async () => {
          await fetchProducts();
          await fetchCategories();
        }}
      />
    </main>"""

assert "</main>" in content, "</main> not found"
content = content.replace("    </main>", editor_mount, 1)
print("Mounted <ProductEditor> before </main>.")

with open(app_path, "w", encoding="utf-8", newline="\r\n") as f:
    f.write(content)

print("Saved App.tsx successfully!")
