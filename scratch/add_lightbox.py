filepath = 'apps/storefront/index.html'
with open(filepath, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Update sign card with click handler & zoom pill
old_sign_card = '''            <!-- Real Boutique Sign & Showcase Image -->
            <div class="lg:col-span-5">
              <div class="relative rounded-2xl overflow-hidden border border-gold-reflective/40 shadow-2xl bg-emerald-forest group">
                <img src="/assets/mus_luxury_sign.jpg" alt="Enseigne officielle Mus Luxury Ouled Yaïch" class="w-full h-72 sm:h-96 object-cover object-center group-hover:scale-105 transition duration-500" />
                <div class="absolute inset-0 bg-gradient-to-t from-emerald-forest/80 via-transparent to-transparent"></div>
                <div class="absolute bottom-4 left-4 right-4 bg-emerald-forest/90 backdrop-blur-md px-4 py-3 rounded-xl border border-gold-reflective/30 flex items-center justify-between">
                  <div>
                    <p class="font-luxury font-bold text-sm text-gold-reflective">Boutique Ouled Yaïch</p>
                    <p class="text-[11px] text-white/80">Façade &amp; Enseigne lumineuse officielle</p>
                  </div>
                  <span class="px-2.5 py-1 rounded-full bg-gold-reflective text-emerald-forest font-bold text-[10px] uppercase">Blida 09</span>
                </div>
              </div>
            </div>'''

new_sign_card = '''            <!-- Real Boutique Sign & Showcase Image with Lightbox Viewer -->
            <div class="lg:col-span-5">
              <div onclick="openSignLightbox()" class="relative rounded-2xl overflow-hidden border border-gold-reflective/40 shadow-2xl bg-emerald-forest group cursor-pointer" title="Cliquer pour afficher la vue haute définition">
                <img src="/assets/mus_luxury_sign.jpg" alt="Enseigne officielle Mus Luxury Ouled Yaïch" class="w-full h-72 sm:h-96 object-cover object-center group-hover:scale-105 transition duration-500" />
                <div class="absolute inset-0 bg-gradient-to-t from-emerald-forest/80 via-transparent to-transparent"></div>
                <div class="absolute top-3 right-3 px-2.5 py-1 rounded-full bg-emerald-deep/90 border border-gold-reflective/40 text-gold-reflective text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 opacity-90 group-hover:opacity-100 transition shadow">
                  <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="11" y1="8" x2="11" y2="14"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg>
                  <span>Agrandir</span>
                </div>
                <div class="absolute bottom-4 left-4 right-4 bg-emerald-forest/90 backdrop-blur-md px-4 py-3 rounded-xl border border-gold-reflective/30 flex items-center justify-between">
                  <div>
                    <p class="font-luxury font-bold text-sm text-gold-reflective">Boutique Ouled Yaïch</p>
                    <p class="text-[11px] text-white/80">Façade &amp; Enseigne lumineuse officielle</p>
                  </div>
                  <span class="px-2.5 py-1 rounded-full bg-gold-reflective text-emerald-forest font-bold text-[10px] uppercase">Blida 09</span>
                </div>
              </div>
            </div>'''

c = c.replace(old_sign_card, new_sign_card)

# 2. Add Lightbox Modal before closing body tag
lightbox_modal = '''  <!-- ===================================================================== -->
  <!-- LIGHTBOX MODAL: AUTHENTIC BOUTIQUE SIGN                              -->
  <!-- ===================================================================== -->
  <div id="maison-photo-lightbox" class="fixed inset-0 z-50 bg-black/90 backdrop-blur-md hidden flex items-center justify-center p-4" onclick="if(event.target===this)closeSignLightbox()">
    <div class="relative max-w-4xl w-full bg-emerald-deep border border-gold-reflective/50 rounded-2xl overflow-hidden shadow-2xl">
      <div class="p-3.5 bg-emerald-forest border-b border-gold-reflective/25 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-gold-reflective"></span>
          <span class="font-luxury text-sm font-bold text-gold-reflective">Maison Mus Luxury • Ouled Yaïch (Blida 09)</span>
        </div>
        <button type="button" onclick="closeSignLightbox()" class="text-gold-light hover:text-white p-1 rounded-lg transition" aria-label="Fermer">
          <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>
      <div class="p-4 flex flex-col items-center justify-center bg-black/60">
        <img src="/assets/mus_luxury_sign.jpg" alt="Façade et Enseigne officielle Mus Luxury" class="max-h-[75vh] w-auto rounded-lg object-contain border border-gold-reflective/30 shadow-2xl" />
        <p class="mt-3 text-xs text-gold-light/90 text-center font-medium">Photographie certifiée de notre boutique physique • FVX6+GCJ Mus luxury, Ouled Yaïch, Blida</p>
      </div>
    </div>
  </div>
'''

if 'id="maison-photo-lightbox"' not in c:
    c = c.replace('<!-- TOAST NOTIFICATION BANNER -->', lightbox_modal + '\n  <!-- TOAST NOTIFICATION BANNER -->')

# 3. Add JS functions
js_funcs = '''
    function openSignLightbox() {
      const el = document.getElementById("maison-photo-lightbox");
      if (el) el.classList.remove("hidden");
    }

    function closeSignLightbox() {
      const el = document.getElementById("maison-photo-lightbox");
      if (el) el.classList.add("hidden");
    }
'''

if 'function openSignLightbox' not in c:
    c = c.replace('function renderLaMaisonPage() {', js_funcs + '\n    function renderLaMaisonPage() {')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(c)

print('Lightbox modal successfully added.')
