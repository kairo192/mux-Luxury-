# scratch/verify_update03_headless.py
import sys
import time
import webview

test_results = []

def run_tests(window):
    time.sleep(2) # Allow DOMContentLoaded and syncStorefrontWithBackend to finish
    
    try:
        # Test 1: Check no duplicate header navigation bar
        dup_nav = window.evaluate_js('document.querySelectorAll("header nav").length')
        has_dup = window.evaluate_js('document.getElementById("dynamic-nav-categories") !== null')
        test_results.append(("No duplicate nav in header", dup_nav == 1 and not has_dup, f"Header nav count: {dup_nav}, has_dup: {has_dup}"))

        # Test 2: Check 4 Desktop Nav Links
        home_btn = window.evaluate_js('document.getElementById("nav-link-home") !== null')
        boutique_btn = window.evaluate_js('document.getElementById("nav-link-boutique") !== null')
        col_btn = window.evaluate_js('document.getElementById("nav-link-collections") !== null')
        maison_btn = window.evaluate_js('document.getElementById("nav-link-maison") !== null')
        test_results.append(("4 Desktop Nav Links present", home_btn and boutique_btn and col_btn and maison_btn, f"Home:{home_btn}, Boutique:{boutique_btn}, Col:{col_btn}, Maison:{maison_btn}"))

        # Test 3: Check Initial Route is Home and Active Indicator on Home
        is_home_active = window.evaluate_js('document.getElementById("nav-link-home").classList.contains("text-gold-reflective")')
        home_sec_visible = window.evaluate_js('!document.getElementById("store-home-sections").classList.contains("hidden")')
        maison_sec_hidden = window.evaluate_js('document.getElementById("store-maison-section").classList.contains("hidden")')
        test_results.append(("Home Route Active on Start", is_home_active and home_sec_visible and maison_sec_hidden, f"Active:{is_home_active}, HomeSec:{home_sec_visible}, MaisonHidden:{maison_sec_hidden}"))

        # Test 4: Navigate to #/maison
        window.evaluate_js('navigateTo("#/maison")')
        time.sleep(0.5)
        hash_val = window.evaluate_js('window.location.hash')
        is_maison_active = window.evaluate_js('document.getElementById("nav-link-maison").classList.contains("text-gold-reflective")')
        is_home_inactive = window.evaluate_js('!document.getElementById("nav-link-home").classList.contains("text-gold-reflective")')
        maison_visible = window.evaluate_js('!document.getElementById("store-maison-section").classList.contains("hidden")')
        home_hidden = window.evaluate_js('document.getElementById("store-home-sections").classList.contains("hidden")')
        test_results.append(("Navigate to #/maison", hash_val == "#/maison" and is_maison_active and is_home_inactive and maison_visible and home_hidden, f"Hash:{hash_val}, MaisonActive:{is_maison_active}, MaisonVis:{maison_visible}"))

        # Test 5: Check La Maison Page Details
        store_addr = window.evaluate_js('document.getElementById("maison-store-address").textContent')
        live_status = window.evaluate_js('document.getElementById("maison-live-status").textContent')
        has_map = window.evaluate_js('document.getElementById("maison-osm-map") !== null')
        test_results.append(("La Maison Page Content", "Ouled Yaïch" in store_addr and len(live_status) > 5 and has_map, f"Address:'{store_addr}', Status:'{live_status}', Map:{has_map}"))

        # Test 6: Navigate to #/boutique
        window.evaluate_js('navigateTo("#/boutique")')
        time.sleep(0.5)
        hash_boutique = window.evaluate_js('window.location.hash')
        boutique_active = window.evaluate_js('document.getElementById("nav-link-boutique").classList.contains("text-gold-reflective")')
        pills_rendered = window.evaluate_js('document.getElementById("catalog-category-pills").children.length > 0')
        catalog_visible = window.evaluate_js('!document.getElementById("catalog-section").classList.contains("hidden")')
        test_results.append(("Navigate to #/boutique", hash_boutique == "#/boutique" and boutique_active and pills_rendered and catalog_visible, f"Hash:{hash_boutique}, Active:{boutique_active}, PillsCount>0:{pills_rendered}"))

        # Test 7: Mobile Navigation Bottom Bar (5 items)
        mob_tabs = window.evaluate_js('document.querySelectorAll("#mobile-bottom-nav .mobile-bottom-tab").length')
        test_results.append(("Mobile Bottom Nav 5 Destinations", mob_tabs == 5, f"Tab count: {mob_tabs}"))

        # Test 8: Mobile Drawer Menu
        window.evaluate_js('openMobileMenu()')
        drawer_open = window.evaluate_js('!document.getElementById("mobile-nav-drawer").classList.contains("hidden")')
        window.evaluate_js('closeMobileMenu()')
        drawer_closed = window.evaluate_js('document.getElementById("mobile-nav-drawer").classList.contains("hidden")')
        test_results.append(("Mobile Drawer Open & Close", drawer_open and drawer_closed, f"Open:{drawer_open}, Closed:{drawer_closed}"))

        # Test 9: Collections Dropdown Populated
        dropdown_items = window.evaluate_js('document.querySelectorAll("#header-collections-dropdown-list button").length')
        test_results.append(("Collections Dropdown Populated", dropdown_items > 0, f"Dropdown items count: {dropdown_items}"))

        # Test 10: Clean Hero Image (Zero duplicated text)
        hero_img_src = window.evaluate_js('document.querySelector("#store-home-sections img")?.src || ""')
        test_results.append(("Hero Image Clean Asset", "hero_bag_clean" in hero_img_src, f"Image src: '{hero_img_src}'"))

        # Test 11: Lightbox Modal for Boutique Sign
        window.evaluate_js('openSignLightbox()')
        lightbox_open = window.evaluate_js('!document.getElementById("maison-photo-lightbox").classList.contains("hidden")')
        window.evaluate_js('closeSignLightbox()')
        lightbox_closed = window.evaluate_js('document.getElementById("maison-photo-lightbox").classList.contains("hidden")')
        test_results.append(("Boutique Sign Lightbox Modal", lightbox_open and lightbox_closed, f"Open:{lightbox_open}, Closed:{lightbox_closed}"))

        print("\n" + "="*70)
        print("REAL BROWSER DOM TEST RESULTS (WEBVIEW2 CHROMIUM)")
        print("="*70)
        all_passed = True
        for name, passed, detail in test_results:
            status = "PASS" if passed else "FAIL"
            print(f"[{status}] {name} - {detail}")
            if not passed:
                all_passed = False
        print("="*70)
        if all_passed:
            print("ALL 11 STOREFRONT BROWSER JOURNEY TESTS PASSED (100% OK)!")
        else:
            print("SOME TESTS FAILED!")
        print("="*70)

    except Exception as e:
        print(f"Exception during test evaluation: {e}")
    finally:
        window.destroy()

if __name__ == "__main__":
    window = webview.create_window(
        "Storefront Test Runner",
        "http://localhost:5173",
        hidden=True, # run headless
        width=1280,
        height=800
    )
    webview.start(run_tests, window)
