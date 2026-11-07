# fix_null_guards.py
with open("apps/storefront/index.html", "r", encoding="utf-8") as f:
    src = f.read()

target = '''      // 1. Category Navigation Bar (if element present)
      const navEl = document.getElementById("dynamic-nav-categories");
      let navHtml = `<button type="button" onclick="navigateStore('home')" class="px-3.5 py-1.5 rounded-full font-semibold transition ${
        state.activeCategorySlug === "all"
          ? "bg-gold-reflective text-emerald-forest font-bold shadow-sm"
          : "text-gold-light/90 hover:text-white hover:bg-emerald-deep"
      }">${t.home}</button>`;

      state.categories.forEach((c) => {
        const isAct = state.activeCategorySlug === c.slug;
        navHtml += `<button type="button" onclick="filterByCategory('${c.slug}')" class="px-3.5 py-1.5 rounded-full font-semibold transition ${
          isAct
            ? "bg-gold-reflective text-emerald-forest font-bold shadow-sm"
            : "text-gold-light/90 hover:text-white hover:bg-emerald-deep"
        }">${catName(c)}</button>`;
      });
      navEl.innerHTML = navHtml;'''

replacement = '''      // 1. Category Navigation Bar (if legacy element present)
      const navEl = document.getElementById("dynamic-nav-categories");
      if (navEl) {
        let navHtml = `<button type="button" onclick="navigateStore('home')" class="px-3.5 py-1.5 rounded-full font-semibold transition ${
          state.activeCategorySlug === "all"
            ? "bg-gold-reflective text-emerald-forest font-bold shadow-sm"
            : "text-gold-light/90 hover:text-white hover:bg-emerald-deep"
        }">${t.home}</button>`;

        state.categories.forEach((c) => {
          const isAct = state.activeCategorySlug === c.slug;
          navHtml += `<button type="button" onclick="filterByCategory('${c.slug}')" class="px-3.5 py-1.5 rounded-full font-semibold transition ${
            isAct
              ? "bg-gold-reflective text-emerald-forest font-bold shadow-sm"
              : "text-gold-light/90 hover:text-white hover:bg-emerald-deep"
          }">${catName(c)}</button>`;
        });
        navEl.innerHTML = navHtml;
      }'''

if target in src:
    src = src.replace(target, replacement)
    with open("apps/storefront/index.html", "w", encoding="utf-8") as f:
        f.write(src)
    print("Guarded navEl successfully!")
else:
    print("Target not found directly.")

