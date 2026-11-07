# -*- coding: utf-8 -*-
"""
apply_update03.py - Full implementation of update 03.md for Mus Luxury Storefront
"""
import re
import sys

def main():
    file_path = "apps/storefront/index.html"
    with open(file_path, "r", encoding="utf-8") as f:
        src = f.read()

    # 1. Update body class to pb-24 md:pb-0
    src = src.replace(
        '<body class="min-h-screen flex flex-col bg-cream text-charcoal pb-16 md:pb-0 selection:bg-gold-reflective selection:text-emerald-forest">',
        '<body class="min-h-screen flex flex-col bg-cream text-charcoal pb-24 md:pb-0 selection:bg-gold-reflective selection:text-emerald-forest">'
    )

    # 2. Update Top Bar Ouled Yaïch link to navigateTo('#/maison')
    old_top_maison = '''        <a href="https://www.google.com/maps/search/?api=1&amp;query=FVX6%2BGCJ+Mus+luxury%2C+Ouled+Ya%C3%AFch" target="_blank" rel="noopener noreferrer" class="hidden xl:inline-flex items-center gap-1 text-gold-light hover:text-gold-reflective transition font-medium" title="FVX6+GCJ Mus luxury, Ouled Yaïch">
          <svg class="w-3.5 h-3.5 text-gold-reflective" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
          <span>Ouled Yaïch</span>
        </a>'''

    new_top_maison = '''        <button type="button" onclick="navigateTo('#/maison')" class="hidden xl:inline-flex items-center gap-1.5 text-gold-light hover:text-gold-reflective transition font-medium" title="Visiter La Maison Mus Luxury à Ouled Yaïch">
          <svg class="w-3.5 h-3.5 text-gold-reflective" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
          <span>Boutique Ouled Yaïch</span>
        </button>'''
    if old_top_maison in src:
        src = src.replace(old_top_maison, new_top_maison)
    else:
        print("Warning: old_top_maison not found directly; searching regex...")
        src = re.sub(
            r'<a href="https://www\.google\.com/maps/search/\?api=1&amp;query=FVX6%2BGCJ[^"]*"[^>]*Ouled Yaïch</a>',
            new_top_maison,
            src
        )

    # 3. Replace Header (eliminate duplicate row, add unified single luxury header)
    header_start_marker = "<!-- ===================================================================== -->\n  <!-- 2. MAIN BOUTIQUE HEADER (LOGO, NAVIGATION, SEARCH, ACTIONS)           -->\n  <!-- ===================================================================== -->"
    header_end_marker = "<!-- ===================================================================== -->\n  <!-- 3. MAIN STOREFRONT CONTENT                                            -->"

    new_header = '''<!-- ===================================================================== -->
  <!-- 2. MAIN BOUTIQUE HEADER (LOGO, NAVIGATION, SEARCH, ACTIONS)           -->
  <!-- ===================================================================== -->
  <header class="bg-emerald-deep text-white sticky top-0 z-40 shadow-luxury border-b border-gold-reflective/25">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 py-2.5 sm:py-3 flex items-center justify-between gap-3 sm:gap-6">

      <!-- Brand Logo -->
      <button type="button" onclick="navigateTo('#/home')" class="flex items-center gap-3 text-left group focus:outline-none flex-shrink-0" aria-label="Accueil Mus Luxury">
        <img src="/assets/mus_luxury_logo.png" alt="Mus Luxury" class="h-9 sm:h-11 w-auto rounded-lg border border-gold-reflective/35 shadow-sm group-hover:border-gold-reflective transition" />
      </button>

      <!-- Desktop Primary Links (Single Clean Unified Row) -->
      <nav class="hidden lg:flex items-center gap-6 xl:gap-8 text-xs uppercase tracking-[0.14em] font-semibold text-gold-light/90" aria-label="Navigation principale">
        <button type="button" onclick="navigateTo('#/home')" id="nav-link-home" class="nav-route-btn text-gold-reflective border-b-2 border-gold-reflective pb-1 transition-all duration-200">Accueil</button>
        <button type="button" onclick="navigateTo('#/boutique')" id="nav-link-boutique" class="nav-route-btn hover:text-gold-reflective pb-1 transition-all duration-200">Boutique</button>
        
        <!-- Collections Dropdown Menu -->
        <div class="relative group" id="collections-dropdown-container">
          <button type="button" id="nav-link-collections" class="nav-route-btn hover:text-gold-reflective pb-1 transition-all duration-200 flex items-center gap-1.5 focus:outline-none">
            <span id="lbl-nav-collections">Collections</span>
            <svg class="w-3.5 h-3.5 text-gold-reflective/80 group-hover:rotate-180 transition-transform duration-200" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
          <!-- Luxury Dropdown Card -->
          <div class="absolute left-0 top-full pt-2 w-72 hidden group-hover:block z-50">
            <div class="bg-emerald-deep/98 backdrop-blur-xl border border-gold-reflective/35 rounded-2xl p-3 shadow-2xl space-y-1">
              <div class="px-3 py-2 border-b border-gold-reflective/20 flex items-center justify-between">
                <span class="text-[10px] uppercase tracking-wider text-gold-reflective font-bold">Nos Univers de Luxe</span>
                <button type="button" onclick="navigateTo('#/boutique')" class="text-[10px] text-gold-light hover:underline font-semibold">Tout voir</button>
              </div>
              <div id="header-collections-dropdown-list" class="max-h-72 overflow-y-auto no-scrollbar py-1 space-y-0.5">
                <!-- Dynamically populated from state.categories -->
              </div>
            </div>
          </div>
        </div>

        <button type="button" onclick="navigateTo('#/maison')" id="nav-link-maison" class="nav-route-btn hover:text-gold-reflective pb-1 transition-all duration-200 flex items-center gap-1.5">
          <svg class="w-3.5 h-3.5 text-gold-reflective" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
            <polyline points="9 22 9 12 15 12 15 22"></polyline>
          </svg>
          <span>La Maison</span>
        </button>
      </nav>

      <!-- Search Bar (Desktop & Tablet) -->
      <div class="hidden md:block flex-1 max-w-xs lg:max-w-sm">
        <div class="relative">
          <input
            type="text"
            id="store-search-input"
            oninput="handleStoreSearch(this.value)"
            placeholder="Rechercher un article..."
            class="w-full pl-4 pr-10 py-1.5 sm:py-2 rounded-full bg-emerald-forest/85 border border-gold-reflective/35 text-xs text-white placeholder-gold-light/55 focus:outline-none focus:border-gold-reflective transition"
          />
          <button type="button" onclick="triggerSearchBtn()" class="absolute inset-y-0 right-0 px-3.5 text-gold-reflective hover:text-gold-light flex items-center" aria-label="Rechercher">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
          </button>
        </div>
      </div>

      <!-- Right Action Icons (Search Mobile, Wishlist, Cart, Mobile Drawer) -->
      <div class="flex items-center gap-2 sm:gap-2.5 flex-shrink-0">
        <!-- Mobile Search Toggle -->
        <button type="button" onclick="toggleMobileSearch()" class="md:hidden w-9 h-9 rounded-full bg-emerald-forest/80 border border-gold-reflective/30 flex items-center justify-center text-gold-light hover:text-gold-reflective transition" aria-label="Recherche">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
        </button>

        <!-- Favorites Button -->
        <button type="button" onclick="navigateTo('#/favoris')" id="btn-header-fav" class="relative h-9 px-3 rounded-full bg-emerald-forest/80 hover:bg-emerald-forest border border-gold-reflective/30 text-gold-light flex items-center gap-1.5 text-xs font-semibold transition" aria-label="Favoris">
          <svg class="w-4 h-4 text-gold-reflective" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
          </svg>
          <span id="fav-count-badge" class="text-[11px] font-bold">0</span>
        </button>

        <!-- Shopping Bag Button -->
        <button type="button" onclick="openCartDrawer()" class="h-9 sm:h-10 px-3.5 sm:px-4 rounded-full gold-cta text-emerald-forest font-bold text-xs flex items-center gap-2 shadow-md transition">
          <svg class="w-4 h-4 stroke-[2.2]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
            <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <path d="M16 10a4 4 0 0 1-8 0"></path>
          </svg>
          <span id="lbl-header-cart" class="hidden sm:inline">Panier</span>
          <span id="cart-count-badge" class="px-1.5 py-0.5 rounded-full bg-emerald-forest text-gold-reflective text-[11px] font-extrabold leading-none">0</span>
        </button>

        <!-- Mobile Drawer Hamburger Toggle Button -->
        <button type="button" onclick="openMobileMenu()" class="lg:hidden w-9 h-9 rounded-full bg-emerald-forest/80 border border-gold-reflective/30 flex items-center justify-center text-gold-light hover:text-gold-reflective transition" aria-label="Menu principal">
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>

    <!-- Collapsible Mobile Search Input -->
    <div id="mobile-search-bar" class="hidden md:hidden px-4 pb-3 bg-emerald-deep">
      <div class="relative">
        <input
          type="text"
          id="mobile-search-input"
          oninput="handleStoreSearch(this.value)"
          placeholder="Rechercher un sac, chaussure, maquillage, montre..."
          class="w-full pl-4 pr-10 py-2 rounded-full bg-emerald-forest border border-gold-reflective/40 text-xs text-white placeholder-gold-light/60 focus:outline-none focus:border-gold-reflective"
        />
        <button type="button" onclick="triggerSearchBtn()" class="absolute inset-y-0 right-0 px-3.5 text-gold-reflective flex items-center" aria-label="Lancer la recherche">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
        </button>
      </div>
    </div>
  </header>

  '''

    h_start = src.find(header_start_marker)
    h_end = src.find(header_end_marker)
    if h_start != -1 and h_end != -1:
        src = src[:h_start] + new_header + src[h_end:]
        print("Header successfully replaced (duplicate row eliminated, clean unified bar installed).")
    else:
        print(f"Error: Header markers not found: h_start={h_start}, h_end={h_end}")
        sys.exit(1)

    # 4. Add Category Quick Filter Pills in #catalog-section
    cat_banner_end_str = '</div>\n\n      <!-- Filter Drawer Trigger (Mobile) + Sort Select -->'
    cat_banner_replacement = '''</div>
      </div>

      <!-- Category Quick Filter Pills (Dynamic from CMS categories) -->
      <div class="flex items-center gap-2 overflow-x-auto no-scrollbar py-1 text-xs whitespace-nowrap" id="catalog-category-pills">
        <!-- Rendered dynamically -->
      </div>

      <!-- Main Boutique Grid: Filters Sidebar + Product Cards -->'''

    # Find the catalog header banner region
    cat_banner_old = re.search(r'(<div class="bg-emerald-deep text-white rounded-2xl p-5 sm:p-6.*?</div>\s*</div>)', src, re.DOTALL)
    if cat_banner_old:
        orig_banner = cat_banner_old.group(1)
        new_banner_block = orig_banner + '\n\n      <!-- Category Quick Filter Pills (Dynamic from CMS categories) -->\n      <div class="flex items-center gap-2 overflow-x-auto no-scrollbar py-1 text-xs whitespace-nowrap" id="catalog-category-pills">\n        <!-- Rendered dynamically from CMS categories -->\n      </div>'
        src = src.replace(orig_banner, new_banner_block, 1)
        print("Category quick filter pills installed in #catalog-section.")
    else:
        print("Warning: Catalog banner container not found with regex.")

    # 5. Insert #store-maison-section in <main> before </main>
    maison_section_html = '''    <!-- =================================================================== -->
    <!-- DEDICATED "LA MAISON" PHYSICAL BOUTIQUE PAGE (#/maison)              -->
    <!-- =================================================================== -->
    <div id="store-maison-section" class="hidden space-y-10 sm:space-y-12">

      <!-- Editorial Hero Banner with Real Boutique Imagery -->
      <section class="hero-luxury-bg text-white border-b border-gold-reflective/30 relative overflow-hidden">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 py-10 sm:py-16">
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
            
            <div class="lg:col-span-7 space-y-4 sm:space-y-6">
              <div class="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-gold-reflective/15 border border-gold-reflective/40 text-gold-light text-[11px] uppercase tracking-[0.22em] font-semibold">
                <svg class="w-3.5 h-3.5 text-gold-reflective" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2L14.8 8.5L22 9.3L16.5 14L18.2 21L12 17.3L5.8 21L7.5 14L2 9.3L9.2 8.5L12 2Z"></path>
                </svg>
                <span>BOUTIQUE PHYSIQUE OFFICIELLE • BLIDA 09</span>
              </div>

              <h1 class="font-luxury text-4xl sm:text-5xl lg:text-6xl font-bold leading-[1.15] tracking-tight">
                <span class="block text-white">La Maison</span>
                <span class="block italic font-normal text-gold-reflective mt-1">Mus Luxury</span>
              </h1>

              <p class="text-sm sm:text-base text-gold-light/90 max-w-xl leading-relaxed">
                L'écrin d'élégance et de raffinement au cœur d'Ouled Yaïch (Blida). Découvrez notre boutique physique exclusive, un espace feutré dédié aux collections prestigieuses de haute maroquinerie, souliers d'art, châles nobles, haute horlogerie et beauté rare.
              </p>

              <!-- Quick Action Buttons -->
              <div class="pt-2 flex flex-wrap items-center gap-3">
                <a href="https://www.google.com/maps/search/?api=1&query=FVX6%2BGCJ+Mus+luxury%2C+Ouled+Ya%C3%AFch" target="_blank" rel="noopener noreferrer" class="px-5 sm:px-6 py-3 rounded-full gold-cta text-emerald-forest font-bold text-xs sm:text-sm uppercase tracking-wider shadow-lg hover:shadow-xl transition flex items-center gap-2">
                  <svg class="w-4 h-4 stroke-[2.2]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="3 11 22 2 13 21 11 13 3 11"></polygon>
                  </svg>
                  <span>Itinéraire Google Maps</span>
                </a>

                <a href="https://wa.me/213655534154?text=Bonjour%20Mus%20Luxury%2C%20je%20souhaite%20des%20informations%20sur%20votre%20boutique%20%C3%A0%20Ouled%20Ya%C3%AFch." target="_blank" rel="noopener noreferrer" class="px-5 sm:px-6 py-3 rounded-full bg-emerald-forest border border-emerald-400/50 hover:bg-emerald-deep text-white font-semibold text-xs sm:text-sm transition flex items-center gap-2">
                  <svg class="w-4 h-4 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                  <span>WhatsApp Boutique</span>
                </a>

                <a href="tel:0655534154" class="px-5 sm:px-6 py-3 rounded-full bg-white/10 hover:bg-white/15 border border-white/25 text-gold-light text-xs sm:text-sm font-semibold transition flex items-center gap-2">
                  <svg class="w-4 h-4 text-gold-reflective" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>
                  <span>0655 53 41 54</span>
                </a>
              </div>
            </div>

            <!-- Real Boutique Sign & Showcase Image -->
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
            </div>

          </div>
        </div>
      </section>

      <!-- Store Identity, Hours & Interactive Map -->
      <section class="max-w-7xl mx-auto px-4 sm:px-6">
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">

          <!-- Left Info Column: Identity, Address, Hours, Live Status -->
          <div class="lg:col-span-5 space-y-6">

            <!-- Address Card -->
            <div class="bg-white rounded-2xl p-6 border border-gold-reflective/30 shadow-luxury space-y-4">
              <div class="flex items-center justify-between border-b border-gray-100 pb-3">
                <div class="flex items-center gap-2">
                  <span class="w-2.5 h-2.5 rounded-full bg-gold-reflective"></span>
                  <h2 class="font-luxury text-lg font-bold text-emerald-deep">Adresse &amp; Localisation</h2>
                </div>
                <!-- Dynamic Live Status Pill -->
                <div id="maison-live-status" class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold">
                  <!-- Populated by JavaScript -->
                </div>
              </div>

              <div class="space-y-3 text-xs">
                <div class="flex items-start gap-3">
                  <div class="w-8 h-8 rounded-full bg-emerald-deep/10 text-emerald-deep flex items-center justify-center flex-shrink-0 mt-0.5">
                    <svg class="w-4 h-4 text-emerald-deep" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                  </div>
                  <div class="flex-1">
                    <p class="font-bold text-charcoal text-sm" id="maison-store-name">Mus Luxury (LUXE)</p>
                    <p class="text-charcoal/80 font-medium mt-0.5" id="maison-store-address">FVX6+GCJ Mus luxury, Ouled Yaïch</p>
                    <p class="text-charcoal/60 text-[11px]">Wilaya de Blida (09), Algérie</p>
                  </div>
                </div>

                <div class="flex items-center gap-2 pt-1">
                  <button type="button" onclick="copyStoreAddress()" class="flex-1 py-2 rounded-xl bg-cream border border-gold-reflective/35 hover:bg-gold-reflective/15 text-emerald-deep text-xs font-semibold flex items-center justify-center gap-1.5 transition">
                    <svg class="w-3.5 h-3.5 text-gold-dark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    <span>Copier l'adresse GPS</span>
                  </button>
                  <a href="https://www.google.com/maps/search/?api=1&query=FVX6%2BGCJ+Mus+luxury%2C+Ouled+Ya%C3%AFch" target="_blank" rel="noopener noreferrer" class="flex-1 py-2 rounded-xl bg-emerald-deep text-gold-reflective hover:bg-emerald-forest text-xs font-semibold flex items-center justify-center gap-1.5 transition shadow">
                    <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="3 11 22 2 13 21 11 13 3 11"></polygon></svg>
                    <span>Google Maps</span>
                  </a>
                </div>
              </div>
            </div>

            <!-- Opening Hours Schedule -->
            <div class="bg-white rounded-2xl p-6 border border-gold-reflective/30 shadow-luxury space-y-4">
              <div class="flex items-center gap-2 border-b border-gray-100 pb-3">
                <svg class="w-4 h-4 text-emerald-deep" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                <h2 class="font-luxury text-lg font-bold text-emerald-deep">Horaires d'Ouverture</h2>
              </div>

              <div class="space-y-2 text-xs">
                <div class="flex items-center justify-between py-1.5 border-b border-gray-100/70">
                  <span class="font-semibold text-charcoal">Samedi</span>
                  <span class="font-mono font-bold text-emerald-deep bg-emerald-50 px-2.5 py-0.5 rounded-lg border border-emerald-200">10h00 – 20h00</span>
                </div>
                <div class="flex items-center justify-between py-1.5 border-b border-gray-100/70">
                  <span class="font-semibold text-charcoal">Dimanche</span>
                  <span class="font-mono font-bold text-emerald-deep bg-emerald-50 px-2.5 py-0.5 rounded-lg border border-emerald-200">10h00 – 20h00</span>
                </div>
                <div class="flex items-center justify-between py-1.5 border-b border-gray-100/70">
                  <span class="font-semibold text-charcoal">Lundi</span>
                  <span class="font-mono font-bold text-emerald-deep bg-emerald-50 px-2.5 py-0.5 rounded-lg border border-emerald-200">10h00 – 20h00</span>
                </div>
                <div class="flex items-center justify-between py-1.5 border-b border-gray-100/70">
                  <span class="font-semibold text-charcoal">Mardi</span>
                  <span class="font-mono font-bold text-emerald-deep bg-emerald-50 px-2.5 py-0.5 rounded-lg border border-emerald-200">10h00 – 20h00</span>
                </div>
                <div class="flex items-center justify-between py-1.5 border-b border-gray-100/70">
                  <span class="font-semibold text-charcoal">Mercredi</span>
                  <span class="font-mono font-bold text-emerald-deep bg-emerald-50 px-2.5 py-0.5 rounded-lg border border-emerald-200">10h00 – 20h00</span>
                </div>
                <div class="flex items-center justify-between py-1.5 border-b border-gray-100/70">
                  <span class="font-semibold text-charcoal">Jeudi</span>
                  <span class="font-mono font-bold text-emerald-deep bg-emerald-50 px-2.5 py-0.5 rounded-lg border border-emerald-200">10h00 – 20h00</span>
                </div>
                <div class="flex items-center justify-between py-1.5 bg-amber-50/60 px-2 rounded-lg border border-amber-200/60">
                  <div class="flex items-center gap-1.5">
                    <span class="font-bold text-amber-900">Vendredi</span>
                    <span class="text-[10px] text-amber-700 font-medium">(Prière du vendredi)</span>
                  </div>
                  <span class="font-mono font-bold text-amber-900 bg-amber-100 px-2.5 py-0.5 rounded-lg border border-amber-300">15h00 – 21h00</span>
                </div>
              </div>
            </div>

            <!-- Direct Contact Card -->
            <div class="bg-white rounded-2xl p-6 border border-gold-reflective/30 shadow-luxury space-y-4">
              <h2 class="font-luxury text-lg font-bold text-emerald-deep border-b border-gray-100 pb-3">Service Clientèle &amp; Réseaux</h2>
              <div class="space-y-3 text-xs">
                <a href="tel:0655534154" class="flex items-center justify-between p-3 rounded-xl bg-cream hover:bg-gold-reflective/15 border border-gold-reflective/25 transition">
                  <div class="flex items-center gap-2.5">
                    <div class="w-7 h-7 rounded-full bg-emerald-deep text-gold-reflective flex items-center justify-center">
                      <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>
                    </div>
                    <div>
                      <span class="font-bold text-charcoal block">Appel Téléphonique Direct</span>
                      <span class="text-charcoal/60 text-[11px]">0655 53 41 54</span>
                    </div>
                  </div>
                  <span class="font-bold text-emerald-deep text-[11px]">Appeler →</span>
                </a>

                <a href="https://wa.me/213655534154" target="_blank" rel="noopener noreferrer" class="flex items-center justify-between p-3 rounded-xl bg-emerald-50 hover:bg-emerald-100/70 border border-emerald-200 transition">
                  <div class="flex items-center gap-2.5">
                    <div class="w-7 h-7 rounded-full bg-emerald-600 text-white flex items-center justify-center">
                      <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                    </div>
                    <div>
                      <span class="font-bold text-emerald-950 block">WhatsApp Officiel</span>
                      <span class="text-emerald-700 text-[11px]">+213 655 53 41 54</span>
                    </div>
                  </div>
                  <span class="font-bold text-emerald-800 text-[11px]">Écrire →</span>
                </a>

                <div class="grid grid-cols-2 gap-2 pt-1">
                  <a href="https://www.instagram.com/musluxury09?rpxt=emk3bjBhdjV5d2Ux" target="_blank" rel="noopener noreferrer" class="p-2.5 rounded-xl bg-cream border border-gold-reflective/25 hover:border-gold-reflective text-center transition">
                    <span class="font-bold text-charcoal block text-[11px]">Instagram</span>
                    <span class="text-[10px] text-gold-dark font-medium">@musluxury09</span>
                  </a>
                  <a href="https://www.tiktok.com/@musluxury.092?_r=1&amp;_t=ZS-9B2mO0gpA7V" target="_blank" rel="noopener noreferrer" class="p-2.5 rounded-xl bg-cream border border-gold-reflective/25 hover:border-gold-reflective text-center transition">
                    <span class="font-bold text-charcoal block text-[11px]">TikTok</span>
                    <span class="text-[10px] text-gold-dark font-medium">@musluxury.092</span>
                  </a>
                </div>
              </div>
            </div>

          </div>

          <!-- Right Column: Interactive Location Map & Visiting Experience -->
          <div class="lg:col-span-7 space-y-6">

            <!-- Interactive Map Container -->
            <div class="bg-white rounded-2xl p-6 border border-gold-reflective/30 shadow-luxury space-y-4">
              <div class="flex items-center justify-between border-b border-gray-100 pb-3">
                <div class="flex items-center gap-2">
                  <svg class="w-4 h-4 text-emerald-deep" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon><line x1="8" y1="2" x2="8" y2="18"></line><line x1="16" y1="6" x2="16" y2="22"></line></svg>
                  <h2 class="font-luxury text-lg font-bold text-emerald-deep">Carte Interactive — Ouled Yaïch (Blida)</h2>
                </div>
                <span class="text-[11px] text-charcoal/60 font-mono">36.5050° N, 2.8595° E</span>
              </div>

              <!-- OpenStreetMap Responsive Embed -->
              <div class="relative w-full h-80 sm:h-[420px] rounded-xl overflow-hidden border border-gold-reflective/35 shadow-inner">
                <iframe
                  id="maison-osm-map"
                  title="Carte interactive Mus Luxury Ouled Yaïch"
                  src="https://www.openstreetmap.org/export/embed.html?bbox=2.8450%2C36.4950%2C2.8750%2C36.5150&amp;layer=mapnik&amp;marker=36.5050%2C2.8595"
                  class="w-full h-full border-0"
                  loading="lazy"
                ></iframe>
                <div class="absolute bottom-3 left-3 right-3 bg-emerald-forest/90 backdrop-blur-md px-3.5 py-2.5 rounded-xl border border-gold-reflective/30 flex items-center justify-between text-white text-xs">
                  <div class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full bg-gold-reflective animate-ping"></span>
                    <span class="font-semibold text-gold-light">Boutique Mus Luxury Ouled Yaïch</span>
                  </div>
                  <a href="https://www.google.com/maps/search/?api=1&query=FVX6%2BGCJ+Mus+luxury%2C+Ouled+Ya%C3%AFch" target="_blank" rel="noopener noreferrer" class="text-gold-reflective hover:underline font-bold text-[11px]">
                    Ouvrir en plein écran ↗
                  </a>
                </div>
              </div>

              <div class="p-3.5 rounded-xl bg-cream/70 border border-gold-reflective/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div>
                  <p class="font-bold text-emerald-deep">Vous arrivez en voiture ou transport ?</p>
                  <p class="text-[11px] text-charcoal/70">La boutique est facilement accessible au centre d'Ouled Yaïch avec stationnement à proximité.</p>
                </div>
                <a href="https://www.google.com/maps/search/?api=1&query=FVX6%2BGCJ+Mus+luxury%2C+Ouled+Ya%C3%AFch" target="_blank" rel="noopener noreferrer" class="px-4 py-2 rounded-lg bg-emerald-deep text-gold-reflective hover:bg-emerald-forest font-semibold text-xs whitespace-nowrap shadow transition flex items-center justify-center gap-1.5">
                  <span>Lancer le GPS</span>
                  <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                </a>
              </div>
            </div>

            <!-- 4 Exclusive In-Store Services -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div class="p-4 rounded-xl bg-white border border-gold-reflective/25 shadow-sm space-y-1.5">
                <div class="w-8 h-8 rounded-lg bg-emerald-deep text-gold-reflective flex items-center justify-center">
                  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                </div>
                <h3 class="font-bold text-emerald-deep text-xs sm:text-sm">Conseil &amp; Stylisme Privé</h3>
                <p class="text-[11px] text-charcoal/70 leading-relaxed">Accompagnement sur-mesure pour accorder vos sacs, souliers et montres à vos tenues d'exception.</p>
              </div>

              <div class="p-4 rounded-xl bg-white border border-gold-reflective/25 shadow-sm space-y-1.5">
                <div class="w-8 h-8 rounded-lg bg-emerald-deep text-gold-reflective flex items-center justify-center">
                  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </div>
                <h3 class="font-bold text-emerald-deep text-xs sm:text-sm">Click &amp; Collect sous 1h</h3>
                <p class="text-[11px] text-charcoal/70 leading-relaxed">Commandez sur le site et retirez votre achat directement en boutique sans frais ni attente.</p>
              </div>

              <div class="p-4 rounded-xl bg-white border border-gold-reflective/25 shadow-sm space-y-1.5">
                <div class="w-8 h-8 rounded-lg bg-emerald-deep text-gold-reflective flex items-center justify-center">
                  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="20 12 20 22 4 22 4 12"></polyline><rect x="2" y="7" width="20" height="5"></rect><line x1="12" y1="22" x2="12" y2="7"></line><path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"></path><path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"></path></svg>
                </div>
                <h3 class="font-bold text-emerald-deep text-xs sm:text-sm">Écrin Signature Offert</h3>
                <p class="text-[11px] text-charcoal/70 leading-relaxed">Chaque article est emballé dans notre packaging luxe raffiné avec ruban doré prestige.</p>
              </div>

              <div class="p-4 rounded-xl bg-white border border-gold-reflective/25 shadow-sm space-y-1.5">
                <div class="w-8 h-8 rounded-lg bg-emerald-deep text-gold-reflective flex items-center justify-center">
                  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="6"></circle><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"></path></svg>
                </div>
                <h3 class="font-bold text-emerald-deep text-xs sm:text-sm">Authenticité &amp; Contrôle 100%</h3>
                <p class="text-[11px] text-charcoal/70 leading-relaxed">Toutes nos pièces sont expertisées rigoureusement avant présentation en rayon.</p>
              </div>
            </div>

            <!-- Return to Boutique CTA -->
            <div class="hero-luxury-bg text-white rounded-2xl p-6 border border-gold-reflective/35 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-luxury">
              <div class="space-y-1">
                <p class="font-luxury text-xl font-bold text-gold-light">Découvrir la boutique en ligne</p>
                <p class="text-xs text-white/80">Consultez l'ensemble de notre catalogue avec livraison dans les 69 Wilayas.</p>
              </div>
              <button type="button" onclick="navigateTo('#/boutique')" class="px-6 py-3 rounded-full gold-cta text-emerald-forest font-bold text-xs uppercase tracking-wider whitespace-nowrap shadow transition">
                Accéder à la boutique →
              </button>
            </div>

          </div>

        </div>
      </section>

    </div>
'''

    main_close = src.find("  </main>")
    if main_close != -1:
        src = src[:main_close] + maison_section_html + "\n" + src[main_close:]
        print("Dedicated #store-maison-section installed in <main>.")
    else:
        print("Error: </main> closing tag not found!")
        sys.exit(1)

    # 6. Update Footer link: "À propos de Mus Luxury" -> "La Maison Mus Luxury"
    src = src.replace(
        '<li><button type="button" onclick="openStaticPageModal(\'about\')" class="hover:text-white transition">À propos de Mus Luxury</button></li>',
        '<li><button type="button" onclick="navigateTo(\'#/maison\')" class="hover:text-white transition">La Maison Mus Luxury (Boutique Ouled Yaïch)</button></li>'
    )

    # 7. Replace Mobile Bottom Nav & add Mobile Navigation Drawer
    mob_nav_start_marker = "<!-- ===================================================================== -->\n  <!-- 5. MOBILE BOTTOM NAVIGATION BAR (Matches 1000590075.png Mobile View)  -->\n  <!-- ===================================================================== -->"
    mob_nav_end_marker = "<!-- ===================================================================== -->\n  <!-- 6. PRODUCT DETAILS MODAL (Matches 1000590000.png PDP)                 -->"

    new_mob_section = '''<!-- ===================================================================== -->
  <!-- LUXURY MOBILE NAVIGATION DRAWER (Slide-in)                           -->
  <!-- ===================================================================== -->
  <div id="mobile-nav-drawer" class="hidden fixed inset-0 z-50 bg-black/75 backdrop-blur-sm transition-opacity" onclick="if(event.target === this) closeMobileMenu()">
    <div class="w-4/5 max-w-xs h-full bg-emerald-deep text-white border-r border-gold-reflective/35 flex flex-col shadow-2xl p-5 space-y-5 overflow-y-auto">
      <div class="flex items-center justify-between border-b border-gold-reflective/25 pb-4">
        <div class="flex items-center gap-2.5">
          <img src="/assets/mus_luxury_logo.png" alt="Mus Luxury" class="h-9 w-auto rounded-lg border border-gold-reflective/35" />
          <span class="font-luxury text-base text-gold-reflective font-bold">Mus Luxury</span>
        </div>
        <button type="button" onclick="closeMobileMenu()" class="w-8 h-8 rounded-full bg-emerald-forest border border-gold-reflective/30 flex items-center justify-center text-gold-reflective hover:text-white" aria-label="Fermer le menu">
          ✕
        </button>
      </div>

      <!-- Main Navigation Links -->
      <nav class="space-y-1.5 text-xs font-semibold uppercase tracking-wider" aria-label="Menu mobile">
        <button type="button" onclick="closeMobileMenu(); navigateTo('#/home');" class="w-full text-left px-3.5 py-2.5 rounded-xl hover:bg-emerald-forest text-gold-light hover:text-white transition flex items-center justify-between">
          <span>Accueil</span>
          <svg class="w-4 h-4 text-gold-reflective" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </button>
        <button type="button" onclick="closeMobileMenu(); navigateTo('#/boutique');" class="w-full text-left px-3.5 py-2.5 rounded-xl hover:bg-emerald-forest text-gold-light hover:text-white transition flex items-center justify-between">
          <span>Boutique (Catalogue complet)</span>
          <svg class="w-4 h-4 text-gold-reflective" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </button>
        <button type="button" onclick="closeMobileMenu(); navigateTo('#/maison');" class="w-full text-left px-3.5 py-2.5 rounded-xl bg-gold-reflective/15 border border-gold-reflective/30 text-gold-reflective font-bold transition flex items-center justify-between">
          <span>La Maison (Boutique Ouled Yaïch)</span>
          <svg class="w-4 h-4 text-gold-reflective" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path></svg>
        </button>
        <button type="button" onclick="closeMobileMenu(); navigateTo('#/favoris');" class="w-full text-left px-3.5 py-2.5 rounded-xl hover:bg-emerald-forest text-gold-light hover:text-white transition flex items-center justify-between">
          <span>Mes Favoris</span>
          <span id="mobile-drawer-fav-count" class="px-2 py-0.5 rounded-full bg-emerald-forest border border-gold-reflective/30 text-gold-reflective text-[10px]">0</span>
        </button>
      </nav>

      <!-- Dynamic Categories in Mobile Drawer -->
      <div class="space-y-2 pt-2 border-t border-gold-reflective/20">
        <span class="text-[10px] uppercase tracking-widest text-gold-reflective font-bold block">Collections &amp; Univers</span>
        <div id="mobile-drawer-categories" class="grid grid-cols-2 gap-2">
          <!-- Populated from state.categories -->
        </div>
      </div>

      <!-- Quick Services -->
      <div class="space-y-1.5 pt-2 border-t border-gold-reflective/20 text-xs">
        <button type="button" onclick="closeMobileMenu(); openWilayaTariffsModal();" class="w-full text-left px-3.5 py-2 rounded-xl text-gold-light/90 hover:text-white hover:bg-emerald-forest transition flex items-center gap-2">
          <svg class="w-4 h-4 text-gold-reflective" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="1" y="3" width="15" height="13" rx="1"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon></svg>
          <span>Tarifs 69 Wilayas</span>
        </button>
        <button type="button" onclick="closeMobileMenu(); openOrderTrackingModal();" class="w-full text-left px-3.5 py-2 rounded-xl text-gold-light/90 hover:text-white hover:bg-emerald-forest transition flex items-center gap-2">
          <svg class="w-4 h-4 text-gold-reflective" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
          <span>Suivre ma commande</span>
        </button>
      </div>

      <!-- Direct Contact & Socials -->
      <div class="mt-auto pt-4 border-t border-gold-reflective/20 space-y-2.5">
        <a href="https://wa.me/213655534154" target="_blank" rel="noopener noreferrer" class="w-full py-2.5 rounded-full bg-emerald-forest border border-emerald-400/50 text-white font-bold text-xs flex items-center justify-center gap-2 shadow transition">
          <svg class="w-4 h-4 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
          <span>WhatsApp : 0655 53 41 54</span>
        </a>
        <a href="tel:0655534154" class="w-full py-2 rounded-full bg-white/5 hover:bg-white/10 border border-gold-reflective/30 text-gold-light text-xs flex items-center justify-center gap-2 transition">
          <span>Appeler le 0655 53 41 54</span>
        </a>
      </div>
    </div>
  </div>

  <!-- ===================================================================== -->
  <!-- 5. MOBILE BOTTOM NAVIGATION BAR (5 Clean Destinations)                -->
  <!-- ===================================================================== -->
  <nav id="mobile-bottom-nav" class="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur-md border-t border-gold-reflective/30 shadow-2xl px-1.5 py-1 grid grid-cols-5 text-[10px] font-semibold text-charcoal/75 pb-[calc(env(safe-area-inset-bottom)+0.25rem)]" aria-label="Navigation mobile basse">
    <!-- 1. Accueil -->
    <button type="button" onclick="navigateTo('#/home')" id="mobile-tab-home" class="mobile-bottom-tab flex flex-col items-center justify-center py-1 text-emerald-deep font-bold transition">
      <svg class="w-5 h-5 mb-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
        <polyline points="9 22 9 12 15 12 15 22"></polyline>
      </svg>
      <span>Accueil</span>
    </button>
    <!-- 2. Boutique -->
    <button type="button" onclick="navigateTo('#/boutique')" id="mobile-tab-boutique" class="mobile-bottom-tab flex flex-col items-center justify-center py-1 hover:text-emerald-deep transition">
      <svg class="w-5 h-5 mb-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <rect x="3" y="3" width="7" height="7"></rect>
        <rect x="14" y="3" width="7" height="7"></rect>
        <rect x="14" y="14" width="7" height="7"></rect>
        <rect x="3" y="14" width="7" height="7"></rect>
      </svg>
      <span>Boutique</span>
    </button>
    <!-- 3. Favoris -->
    <button type="button" onclick="navigateTo('#/favoris')" id="mobile-tab-favoris" class="mobile-bottom-tab flex flex-col items-center justify-center py-1 hover:text-emerald-deep transition relative">
      <div class="relative">
        <svg class="w-5 h-5 mb-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
        </svg>
        <span id="mobile-fav-count-badge" class="absolute -top-1 -right-2 px-1 py-0.2 rounded-full bg-emerald-deep text-gold-reflective text-[9px] font-bold leading-none min-w-[14px] text-center">0</span>
      </div>
      <span>Favoris</span>
    </button>
    <!-- 4. Panier -->
    <button type="button" onclick="openCartDrawer()" id="mobile-tab-cart" class="mobile-bottom-tab flex flex-col items-center justify-center py-1 hover:text-emerald-deep transition relative">
      <div class="relative">
        <svg class="w-5 h-5 mb-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path>
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <path d="M16 10a4 4 0 0 1-8 0"></path>
        </svg>
        <span id="mobile-cart-count-badge" class="absolute -top-1 -right-2 px-1 py-0.2 rounded-full bg-emerald-deep text-gold-reflective text-[9px] font-bold leading-none min-w-[14px] text-center">0</span>
      </div>
      <span>Panier</span>
    </button>
    <!-- 5. La Maison -->
    <button type="button" onclick="navigateTo('#/maison')" id="mobile-tab-maison" class="mobile-bottom-tab flex flex-col items-center justify-center py-1 hover:text-emerald-deep transition">
      <svg class="w-5 h-5 mb-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
        <circle cx="12" cy="10" r="3"></circle>
      </svg>
      <span>La Maison</span>
    </button>
  </nav>

  '''

    m_start = src.find(mob_nav_start_marker)
    m_end = src.find(mob_nav_end_marker)
    if m_start != -1 and m_end != -1:
        src = src[:m_start] + new_mob_section + src[m_end:]
        print("Mobile bottom nav (5 clean destinations) & mobile navigation drawer successfully installed.")
    else:
        print(f"Error: Mobile nav markers not found: m_start={m_start}, m_end={m_end}")
        sys.exit(1)

    # 8. Add Router & Supporting JavaScript Functions
    # Let's locate `function navigateStore(target) {`
    old_nav_code = '''    function navigateStore(target) {
      if (target === "home") {
        state.activeCategorySlug = "all";
        state.onlyFavorites = false;
        state.dynamicFilterSelections = {};
        document.getElementById("store-home-sections").classList.remove("hidden");
      }
      renderStorefront();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    function filterByCategory(slug) {
      state.activeCategorySlug = slug;
      state.onlyFavorites = false;
      state.dynamicFilterSelections = {};
      if (slug === "all") {
        document.getElementById("store-home-sections").classList.remove("hidden");
      } else {
        document.getElementById("store-home-sections").classList.add("hidden");
      }
      renderStorefront();
      const catSec = document.getElementById("catalog-section");
      if (catSec && slug !== "all") {
        catSec.scrollIntoView({ behavior: "smooth" });
      }
    }'''

    new_nav_code = '''    // =========================================================================
    // CLIENT-SIDE HASH ROUTER & ACTIVE INDICATOR CONTROLLER
    // =========================================================================
    function navigateTo(hash, pushState = true) {
      if (pushState) {
        if (window.location.hash !== hash) {
          window.location.hash = hash;
          return; // hashchange listener will fire handleRoute()
        }
      }
      handleRoute();
    }

    function updateActiveNavIndicators(hash) {
      // 1. Desktop Nav Links
      const desktopLinks = [
        { id: "nav-link-home", match: hash === "#/home" || hash === "#" || hash === "" },
        { id: "nav-link-boutique", match: hash === "#/boutique" },
        { id: "nav-link-collections", match: hash.startsWith("#/category/") },
        { id: "nav-link-maison", match: hash === "#/maison" },
      ];

      desktopLinks.forEach((link) => {
        const el = document.getElementById(link.id);
        if (!el) return;
        if (link.match) {
          el.className = "nav-route-btn text-gold-reflective border-b-2 border-gold-reflective pb-1 font-bold transition-all duration-200 flex items-center gap-1.5";
        } else {
          el.className = "nav-route-btn text-gold-light/90 hover:text-gold-reflective pb-1 font-semibold transition-all duration-200 flex items-center gap-1.5";
        }
      });

      // 2. Mobile Bottom Nav Tabs
      const mobileTabs = [
        { id: "mobile-tab-home", match: hash === "#/home" || hash === "#" || hash === "" },
        { id: "mobile-tab-boutique", match: hash === "#/boutique" || hash.startsWith("#/category/") },
        { id: "mobile-tab-favoris", match: hash === "#/favoris" },
        { id: "mobile-tab-maison", match: hash === "#/maison" },
      ];

      mobileTabs.forEach((tab) => {
        const el = document.getElementById(tab.id);
        if (!el) return;
        if (tab.match) {
          el.classList.add("text-emerald-deep", "font-bold");
          el.classList.remove("text-charcoal/75", "font-semibold");
        } else {
          el.classList.remove("text-emerald-deep", "font-bold");
          el.classList.add("text-charcoal/75", "font-semibold");
        }
      });
    }

    function handleRoute() {
      const hash = window.location.hash || "#/home";
      const homeSec = document.getElementById("store-home-sections");
      const maisonSec = document.getElementById("store-maison-section");
      const catalogSec = document.getElementById("catalog-section");

      updateActiveNavIndicators(hash);

      if (hash === "#/maison") {
        if (homeSec) homeSec.classList.add("hidden");
        if (catalogSec) catalogSec.classList.add("hidden");
        if (maisonSec) maisonSec.classList.remove("hidden");
        renderLaMaisonPage();
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }

      // Hide Maison if not on #/maison
      if (maisonSec) maisonSec.classList.add("hidden");

      if (hash.startsWith("#/category/")) {
        const slug = hash.replace("#/category/", "").trim();
        state.activeCategorySlug = slug;
        state.onlyFavorites = false;
        if (homeSec) homeSec.classList.add("hidden");
        if (catalogSec) catalogSec.classList.remove("hidden");
        renderStorefront();
        if (catalogSec) catalogSec.scrollIntoView({ behavior: "smooth" });
        return;
      }

      if (hash === "#/favoris") {
        state.onlyFavorites = true;
        if (homeSec) homeSec.classList.add("hidden");
        if (catalogSec) catalogSec.classList.remove("hidden");
        renderStorefront();
        if (catalogSec) catalogSec.scrollIntoView({ behavior: "smooth" });
        return;
      }

      if (hash === "#/boutique") {
        state.activeCategorySlug = "all";
        state.onlyFavorites = false;
        if (homeSec) homeSec.classList.add("hidden");
        if (catalogSec) catalogSec.classList.remove("hidden");
        renderStorefront();
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }

      if (hash === "#/suivi") {
        openOrderTrackingModal();
        return;
      }

      if (hash === "#/tarifs") {
        openWilayaTariffsModal();
        return;
      }

      // Default: #/home
      state.activeCategorySlug = "all";
      state.onlyFavorites = false;
      if (homeSec) homeSec.classList.remove("hidden");
      if (catalogSec) catalogSec.classList.remove("hidden");
      renderStorefront();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    window.addEventListener("hashchange", handleRoute);

    function navigateStore(target) {
      if (target === "home") {
        navigateTo("#/home");
      } else if (target === "boutique" || target === "shop") {
        navigateTo("#/boutique");
      } else if (target === "maison") {
        navigateTo("#/maison");
      } else {
        navigateTo("#/home");
      }
    }

    function filterByCategory(slug) {
      if (slug === "all") {
        navigateTo("#/boutique");
      } else {
        navigateTo("#/category/" + slug);
      }
    }

    function getAlgeriaCurrentTime() {
      // Algeria is UTC+1 all year (no DST)
      const now = new Date();
      const utc = now.getTime() + now.getTimezoneOffset() * 60000;
      return new Date(utc + 3600000);
    }

    function renderLaMaisonPage() {
      const algNow = getAlgeriaCurrentTime();
      const day = algNow.getDay(); // 0 = Sunday, 5 = Friday, 6 = Saturday
      const hour = algNow.getHours();
      const min = algNow.getMinutes();
      const timeNum = hour + min / 60;

      let isOpen = false;
      let closeTimeStr = "";
      let nextOpenStr = "";

      if (day === 5) {
        // Friday: 15h00 - 21h00
        if (timeNum >= 15 && timeNum < 21) {
          isOpen = true;
          closeTimeStr = "21h00";
        } else {
          nextOpenStr = timeNum < 15 ? "aujourd'hui à 15h00" : "demain (samedi) à 10h00";
        }
      } else {
        // Saturday to Thursday: 10h00 - 20h00
        if (timeNum >= 10 && timeNum < 20) {
          isOpen = true;
          closeTimeStr = "20h00";
        } else {
          nextOpenStr = timeNum < 10 ? "aujourd'hui à 10h00" : (day === 4 ? "demain (vendredi) à 15h00" : "demain à 10h00");
        }
      }

      const statusEl = document.getElementById("maison-live-status");
      if (statusEl) {
        if (isOpen) {
          statusEl.className = "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-900 border border-emerald-300";
          statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-600 animate-pulse"></span><span>Ouvert actuellement (Ferme à ${closeTimeStr})</span>`;
        } else {
          statusEl.className = "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-amber-100 text-amber-900 border border-amber-300";
          statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-600"></span><span>Fermé actuellement (Ouvre ${nextOpenStr})</span>`;
        }
      }
    }

    function copyStoreAddress() {
      const addr = "FVX6+GCJ Mus luxury, Ouled Yaïch, Blida (Wilaya 09), Algérie";
      navigator.clipboard?.writeText(addr).then(() => {
        showToast("✓ Adresse GPS copiée dans le presse-papier !");
      }).catch(() => {
        showToast("Adresse : FVX6+GCJ Mus luxury, Ouled Yaïch");
      });
    }

    function renderHeaderCollections() {
      // 1. Header Dropdown List
      const dropdownEl = document.getElementById("header-collections-dropdown-list");
      if (dropdownEl) {
        dropdownEl.innerHTML = state.categories.map((c) => `
          <button type="button" onclick="navigateTo('#/category/${c.slug}')" class="w-full text-left px-3 py-2 rounded-xl hover:bg-emerald-forest transition flex items-center justify-between group">
            <div class="flex items-center gap-2.5">
              <img src="${c.image}" alt="${catName(c)}" class="w-7 h-7 rounded-lg object-cover border border-gold-reflective/30" onerror="this.src='${ASSET_MAP.cat_sacs}'" />
              <span class="text-xs text-white group-hover:text-gold-reflective font-medium transition">${catName(c)}</span>
            </div>
            <svg class="w-3.5 h-3.5 text-gold-reflective/60 group-hover:text-gold-reflective group-hover:translate-x-1 transition" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
          </button>
        `).join("");
      }

      // 2. Catalog Category Quick Filter Pills
      const pillsEl = document.getElementById("catalog-category-pills");
      if (pillsEl) {
        const isAll = state.activeCategorySlug === "all";
        let pillsHtml = `
          <button type="button" onclick="navigateTo('#/boutique')" class="px-3.5 py-1.5 rounded-full font-semibold transition ${
            isAll
              ? "bg-emerald-deep text-gold-reflective border border-gold-reflective shadow-sm font-bold"
              : "bg-white/80 hover:bg-white text-charcoal/80 border border-gold-reflective/25 hover:border-gold-reflective"
          }">Toutes les collections</button>
        `;

        state.categories.forEach((c) => {
          const isAct = state.activeCategorySlug === c.slug;
          pillsHtml += `
            <button type="button" onclick="navigateTo('#/category/${c.slug}')" class="px-3.5 py-1.5 rounded-full font-semibold transition ${
              isAct
                ? "bg-emerald-deep text-gold-reflective border border-gold-reflective shadow-sm font-bold"
                : "bg-white/80 hover:bg-white text-charcoal/80 border border-gold-reflective/25 hover:border-gold-reflective"
            }">${catName(c)}</button>
          `;
        });
        pillsEl.innerHTML = pillsHtml;
      }

      // 3. Mobile Drawer Categories
      const drawerCatsEl = document.getElementById("mobile-drawer-categories");
      if (drawerCatsEl) {
        drawerCatsEl.innerHTML = state.categories.map((c) => `
          <button type="button" onclick="closeMobileMenu(); navigateTo('#/category/${c.slug}');" class="p-2 rounded-xl bg-emerald-forest/80 hover:bg-emerald-forest border border-gold-reflective/25 text-left transition flex items-center gap-2 group">
            <img src="${c.image}" alt="${catName(c)}" class="w-6 h-6 rounded-md object-cover border border-gold-reflective/30" onerror="this.src='${ASSET_MAP.cat_sacs}'" />
            <span class="text-[11px] text-white group-hover:text-gold-reflective font-medium truncate">${catName(c)}</span>
          </button>
        `).join("");
      }
    }

    function openMobileMenu() {
      const drawer = document.getElementById("mobile-nav-drawer");
      if (drawer) drawer.classList.remove("hidden");
    }

    function closeMobileMenu() {
      const drawer = document.getElementById("mobile-nav-drawer");
      if (drawer) drawer.classList.add("hidden");
    }'''

    if old_nav_code in src:
        src = src.replace(old_nav_code, new_nav_code)
        print("Hash router, active indicator controller, and La Maison renderer installed.")
    else:
        print("Warning: old_nav_code not found directly; searching substring...")
        # Fallback replacement
        idx_nav = src.find("function navigateStore(target) {")
        idx_cat = src.find("function scrollToCatalog() {", idx_nav)
        if idx_nav != -1 and idx_cat != -1:
            src = src[:idx_nav] + new_nav_code + "\n\n    " + src[idx_cat:]
            print("Fallback replacement for nav code succeeded.")
        else:
            print("Error: Could not locate navigateStore function.")
            sys.exit(1)

    # 9. In renderStorefront():
    # Update badges on mobile, call renderHeaderCollections()
    old_render_part = '''      const totalCartCount = state.cart.reduce((sum, item) => sum + item.quantity, 0);
      document.getElementById("cart-count-badge").textContent = totalCartCount;

      // 1. Category Navigation Bar
      const navEl = document.getElementById("dynamic-nav-categories");'''

    new_render_part = '''      const totalCartCount = state.cart.reduce((sum, item) => sum + item.quantity, 0);
      document.getElementById("cart-count-badge").textContent = totalCartCount;
      const mobCartBadge = document.getElementById("mobile-cart-count-badge");
      if (mobCartBadge) mobCartBadge.textContent = totalCartCount;
      const mobFavBadge = document.getElementById("mobile-fav-count-badge");
      if (mobFavBadge) mobFavBadge.textContent = state.favorites.size;
      const mobDrawerFav = document.getElementById("mobile-drawer-fav-count");
      if (mobDrawerFav) mobDrawerFav.textContent = state.favorites.size;

      // Render Dynamic Collections & Category Pills
      renderHeaderCollections();

      // 1. Category Navigation Bar (if element present)
      const navEl = document.getElementById("dynamic-nav-categories");'''

    if old_render_part in src:
        src = src.replace(old_render_part, new_render_part)
        print("renderStorefront updated with mobile badge sync & renderHeaderCollections().")
    else:
        print("Warning: old_render_part not found directly; trying flexible replacement...")
        src = src.replace(
            'document.getElementById("cart-count-badge").textContent = totalCartCount;',
            'document.getElementById("cart-count-badge").textContent = totalCartCount;\n      const mobCartBadge = document.getElementById("mobile-cart-count-badge");\n      if (mobCartBadge) mobCartBadge.textContent = totalCartCount;\n      const mobFavBadge = document.getElementById("mobile-fav-count-badge");\n      if (mobFavBadge) mobFavBadge.textContent = state.favorites.size;\n      renderHeaderCollections();'
        )

    # 10. In syncStorefrontWithBackend(): fetch /api/v1/store/settings
    old_sync_promises = '''        const [catRes, prodRes, wilRes] = await Promise.all([
          fetch("/api/v1/categories").then((r) => (r.ok ? r.json() : null)).catch(() => null),
          fetch("/api/v1/products?page_size=50").then((r) => (r.ok ? r.json() : null)).catch(() => null),
          fetch("/api/v1/delivery-zones").then((r) => (r.ok ? r.json() : null)).catch(() => null),
        ]);'''

    new_sync_promises = '''        const [catRes, prodRes, wilRes, setRes] = await Promise.all([
          fetch("/api/v1/categories").then((r) => (r.ok ? r.json() : null)).catch(() => null),
          fetch("/api/v1/products?page_size=50").then((r) => (r.ok ? r.json() : null)).catch(() => null),
          fetch("/api/v1/delivery-zones").then((r) => (r.ok ? r.json() : null)).catch(() => null),
          fetch("/api/v1/store/settings").then((r) => (r.ok ? r.json() : null)).catch(() => null),
        ]);'''

    if old_sync_promises in src:
        src = src.replace(old_sync_promises, new_sync_promises)
        print("syncStorefrontWithBackend updated to fetch /api/v1/store/settings.")

    # Apply dynamic settings if present
    old_sync_apply = '''        if (dataChanged || !state.isCatalogLoaded) {
          state.isCatalogLoaded = true;
          renderStorefront();
        }'''

    new_sync_apply = '''        if (setRes && typeof setRes === "object") {
          state.storeSettings = setRes;
          if (setRes.store_phone) {
            const el = document.getElementById("maison-store-phone");
            if (el) el.textContent = setRes.store_phone;
          }
          if (setRes.store_location) {
            const el = document.getElementById("maison-store-address");
            if (el) el.textContent = setRes.store_location;
          }
        }
        if (dataChanged || !state.isCatalogLoaded) {
          state.isCatalogLoaded = true;
          renderStorefront();
        }'''

    if old_sync_apply in src:
        src = src.replace(old_sync_apply, new_sync_apply)
        print("Applied dynamic storeSettings handling in syncStorefrontWithBackend.")

    # 11. In DOMContentLoaded: call handleRoute()
    old_dom_loaded = '''    window.addEventListener("DOMContentLoaded", () => {
      renderStorefront();
      syncStorefrontWithBackend();'''

    new_dom_loaded = '''    window.addEventListener("DOMContentLoaded", () => {
      renderStorefront();
      handleRoute();
      syncStorefrontWithBackend();'''

    if old_dom_loaded in src:
        src = src.replace(old_dom_loaded, new_dom_loaded)
        print("DOMContentLoaded updated with handleRoute().")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(src)
    print("Done! apps/storefront/index.html updated successfully.")

if __name__ == "__main__":
    main()

