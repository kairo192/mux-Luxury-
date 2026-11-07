import os

filepath = 'apps/storefront/index.html'
with open(filepath, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Hero banner clean image
c = c.replace(
    '<img src="/assets/hero_banner_mus.jpg" alt="Collection Mus Luxury" fetchpriority="high" decoding="async" class="w-full h-52 sm:h-72 lg:h-[370px] object-cover object-center" />',
    '<img src="/assets/hero_bag_clean.jpg" alt="Collection Mus Luxury — Maroquinerie d\'Exception" fetchpriority="high" decoding="async" class="w-full h-52 sm:h-72 lg:h-[370px] object-cover object-center" />'
)
c = c.replace('hero: "/assets/hero_banner_mus.jpg",', 'hero: "/assets/hero_bag_clean.jpg",')

# 2. Translations clean
c = c.replace('scenarioBSame: "✓ Oui, mêmes options",', 'scenarioBSame: "Oui, mêmes options",')
c = c.replace('scenarioBSplit: "⚡ Non, choisir les options séparément",', 'scenarioBSplit: "Personnaliser chaque article séparément",')
c = c.replace('scenarioBComplete: "✓ Répartition complète ({qty}/{qty})"', 'scenarioBComplete: "Répartition complète ({qty}/{qty})"')

c = c.replace('scenarioBSame: "✓ نعم، نفس الخيارات",', 'scenarioBSame: "نعم، نفس الخيارات",')
c = c.replace('scenarioBSplit: "⚡ لا، اختيار الخيارات بشكل منفصل",', 'scenarioBSplit: "تخصيص كل قطعة على حدة",')
c = c.replace('scenarioBComplete: "✓ اكتمل التوزيع ({qty}/{qty})"', 'scenarioBComplete: "اكتمل التوزيع ({qty}/{qty})"')

c = c.replace('scenarioBSame: "✓ Yes, same options",', 'scenarioBSame: "Yes, same options",')
c = c.replace('scenarioBSplit: "⚡ No, choose options separately",', 'scenarioBSplit: "Customize each item separately",')
c = c.replace('scenarioBComplete: "✓ Full allocation complete ({qty}/{qty})"', 'scenarioBComplete: "Full allocation complete ({qty}/{qty})"')

# 3. Badges
c = c.replace('badge.textContent = "⛔ Vérification Requise — Mus Luxury";', 'badge.textContent = "Vérification requise — Maison Mus Luxury";')
c = c.replace('badge.textContent = "✨ Maison Mus Luxury — Conciergerie";', 'badge.textContent = "Maison Mus Luxury — Conciergerie Officielle";')

# 4. PDP Scenario B buttons
c = c.replace('${tr.scenarioBSame || "✓ Oui, mêmes options"}', '${tr.scenarioBSame || "Oui, mêmes options"}')
c = c.replace('${tr.scenarioBSplit || "⚡ Non, choisir les options séparément"}', '${tr.scenarioBSplit || "Personnaliser chaque article séparément"}')
c = c.replace('✓ Répartition complète (${state.activePdpQty}/${state.activePdpQty})', 'Répartition complète (${state.activePdpQty}/${state.activePdpQty})')

# 5. Free shipping text
c = c.replace('? "✨ Livraison Prioritaire Offerte débloquée (Commande ≥ 25 000 DA)"', '? "Livraison Prioritaire Offerte débloquée (Commande ≥ 25 000 DA)"')

# 6. WhatsApp Concierge button with SVG icon
old_wa = '<span>💬 Commander en 1 clic via Conciergerie WhatsApp (0655 53 41 54)</span>'
new_wa = '<svg class="w-4 h-4 text-emerald-700 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor"><path d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.816 9.816 0 0 0 12.04 2m.01 1.67c2.2 0 4.26.86 5.82 2.42a8.225 8.225 0 0 1 2.41 5.83c0 4.54-3.7 8.24-8.24 8.24-1.48 0-2.93-.4-4.2-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.196 8.196 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.24-8.24m4.52 11.66c-.25-.13-1.47-.72-1.7-.81-.23-.08-.39-.13-.56.13-.17.25-.64.81-.79.97-.14.17-.29.19-.54.06-.25-.13-1.06-.39-2.03-1.25-.75-.67-1.26-1.5-1.41-1.75-.15-.25-.02-.39.11-.51.11-.11.25-.29.37-.44.13-.14.17-.25.25-.42.08-.17.04-.31-.02-.44-.06-.13-.56-1.34-.76-1.84-.2-.49-.4-.42-.56-.43h-.48c-.17 0-.44.06-.67.31-.23.25-.88.86-.88 2.1s.9 2.43 1.03 2.6c.13.17 1.77 2.7 4.29 3.79.6.26 1.07.41 1.44.53.6.19 1.15.16 1.58.1.48-.07 1.47-.6 1.68-1.18.21-.58.21-1.07.15-1.18-.06-.1-.23-.17-.48-.29z"/></svg><span>Commander en 1 clic via Conciergerie WhatsApp (0655 53 41 54)</span>'
c = c.replace(old_wa, new_wa)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(c)

print('Updated apps/storefront/index.html successfully.')
