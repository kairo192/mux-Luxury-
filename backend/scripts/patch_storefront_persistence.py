import re

sf_path = r"c:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce\apps\storefront\index.html"

with open(sf_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Initialize favorites and cart from localStorage
old_state = """      favorites: new Set(),
      cart: [],"""

new_state = """      favorites: (() => {
        try {
          const raw = localStorage.getItem("luxe_store_favorites");
          return raw ? new Set(JSON.parse(raw)) : new Set();
        } catch (_e) {
          return new Set();
        }
      })(),
      cart: (() => {
        try {
          const raw = localStorage.getItem("luxe_store_cart");
          return raw ? JSON.parse(raw) : [];
        } catch (_e) {
          return [];
        }
      })(),"""

assert old_state in code, "old_state not found"
code = code.replace(old_state, new_state, 1)
print("1. Initialized cart & favorites from localStorage.")

# 2. Add storage persistence helper functions
old_format = """    function formatDZD(amount) {"""

new_format = """    function saveCartToStorage() {
      try {
        localStorage.setItem("luxe_store_cart", JSON.stringify(state.cart));
      } catch (_e) {}
    }

    function saveFavoritesToStorage() {
      try {
        localStorage.setItem("luxe_store_favorites", JSON.stringify([...state.favorites]));
      } catch (_e) {}
    }

    function formatDZD(amount) {"""

assert old_format in code, "old_format not found"
code = code.replace(old_format, new_format, 1)
print("2. Added saveCartToStorage & saveFavoritesToStorage helpers.")

# 3. Add saveFavoritesToStorage in toggleFavoriteProduct
old_fav = """    function toggleFavoriteProduct(prodId) {
      if (state.favorites.has(prodId)) {
        state.favorites.delete(prodId);
      } else {
        state.favorites.add(prodId);
        showToast("Article ajouté à vos favoris");
      }
      document.getElementById("fav-count-badge").textContent = state.favorites.size;
      renderCatalogProducts();
    }"""

new_fav = """    function toggleFavoriteProduct(prodId) {
      if (state.favorites.has(prodId)) {
        state.favorites.delete(prodId);
      } else {
        state.favorites.add(prodId);
        showToast("Article ajouté à vos favoris");
      }
      saveFavoritesToStorage();
      document.getElementById("fav-count-badge").textContent = state.favorites.size;
      renderCatalogProducts();
    }"""

assert old_fav in code, "old_fav not found"
code = code.replace(old_fav, new_fav, 1)
print("3. Updated toggleFavoriteProduct with localStorage save.")

# 4. Add saveCartToStorage in addToCartInternal
old_add = """      if (existing) {
        existing.quantity += qty;
      } else {
        state.cart.push({ variantId, productId: prodId, quantity: qty });
      }
      state.lastConfirmedOrder = null;
      renderStorefront();
      if (notify) showToast(`${prodName(prod)} (${variant.title}) ajouté au panier`);"""

new_add = """      if (existing) {
        existing.quantity += qty;
      } else {
        state.cart.push({ variantId, productId: prodId, quantity: qty });
      }
      saveCartToStorage();
      state.lastConfirmedOrder = null;
      renderStorefront();
      if (notify) showToast(`${prodName(prod)} (${variant.title}) ajouté au panier`);"""

assert old_add in code, "old_add not found"
code = code.replace(old_add, new_add, 1)
print("4. Updated addToCartInternal with localStorage save.")

# 5. Add saveCartToStorage in updateCartItemQty
old_update_qty = """      if (next <= 0) {
        state.cart.splice(idx, 1);
      } else if (variant && next <= variant.stock) {
        item.quantity = next;
      } else {
        showToast("Quantité maximale en stock atteinte", "error");
      }
      renderStorefront();
      renderCartDrawerContent();"""

new_update_qty = """      if (next <= 0) {
        state.cart.splice(idx, 1);
      } else if (variant && next <= variant.stock) {
        item.quantity = next;
      } else {
        showToast("Quantité maximale en stock atteinte", "error");
      }
      saveCartToStorage();
      renderStorefront();
      renderCartDrawerContent();"""

assert old_update_qty in code, "old_update_qty not found"
code = code.replace(old_update_qty, new_update_qty, 1)
print("5. Updated updateCartItemQty with localStorage save.")

# 6. Clear cart storage upon order confirmation
old_order_clear = """      state.orders.unshift(newOrder);
      state.cart = [];
      state.appliedCoupon = null;"""

new_order_clear = """      state.orders.unshift(newOrder);
      state.cart = [];
      saveCartToStorage();
      state.appliedCoupon = null;"""

assert old_order_clear in code, "old_order_clear not found"
code = code.replace(old_order_clear, new_order_clear, 1)
print("6. Updated order confirmation with cart storage cleanup.")

with open(sf_path, "w", encoding="utf-8", newline="\r\n") as f:
    f.write(code)

print("Saved storefront persistence patch successfully!")
