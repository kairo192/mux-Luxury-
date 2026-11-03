from pathlib import Path

p = Path(r"c:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce\apps\storefront\index.html")
c = p.read_text(encoding="utf-8")
needle = 'const homeGrid = document.getElementById("home-categories-grid");'
idx1 = c.find(needle)
idx2 = c.find('.join("");', idx1)

if idx1 != -1 and idx2 != -1:
    old_block = c[idx1:idx2 + len('.join("");')]
    new_block = """const homeGrid = document.getElementById("home-categories-grid");
      if (homeGrid) {
        if (state.categories.length === 0) {
          homeGrid.innerHTML = `
            <div class="col-span-full bg-white/60 backdrop-blur rounded-2xl p-8 text-center border border-gold-reflective/20">
              <p class="font-serif italic text-emerald-deep font-medium">Aucune catégorie disponible pour le moment.</p>
            </div>
          `;
        } else {
          homeGrid.innerHTML = state.categories
            .map((c) => {
              return `
                <button type="button" onclick="filterByCategory('${c.slug}')" class="h-full group cat-card-bg rounded-xl sm:rounded-2xl overflow-hidden border border-gold-reflective/35 shadow-luxury hover:shadow-luxury-hover hover:border-gold-reflective transition text-center flex flex-col justify-between">
                  <div class="aspect-[4/3] w-full overflow-hidden bg-emerald-forest relative">
                    <img src="${c.image}" alt="${catName(c)}" loading="lazy" decoding="async" class="w-full h-full object-cover group-hover:scale-105 transition duration-500" />
                    <div class="absolute inset-0 bg-gradient-to-t from-emerald-forest/75 via-transparent to-transparent"></div>
                  </div>
                  <div class="w-full px-1.5 sm:px-2 py-2 sm:py-2.5 flex items-center justify-center gap-1.5 bg-emerald-forest/95 border-t border-gold-reflective/20">
                    <span class="w-1.5 h-1.5 rounded-full bg-gold-reflective flex-shrink-0"></span>
                    <span class="font-semibold text-[11px] sm:text-xs text-white group-hover:text-gold-reflective truncate transition">${catName(c)}</span>
                  </div>
                </button>
              `;
            })
            .join("");
        }
      }"""
    c = c[:idx1] + new_block + c[idx2 + len('.join("");'):]
    p.write_text(c, encoding="utf-8")
    print("Successfully patched homeGrid!")
else:
    print("Indices not found!")
