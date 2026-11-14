import { useRef } from "react";
import { AlertTriangle, Archive, ShoppingBag, Trash2, X } from "lucide-react";
import { mediaUrl } from "../api/adminClient";
import { useModalFocus } from "../utils/useModalFocus";

interface Props {
  productToDelete: any | null;
  deletingProduct: boolean;
  error: string;
  setProductToDelete: (p: any | null) => void;
  setError: (msg: string) => void;
  handleConfirmDeleteProduct: (hard: boolean) => void;
}

/** Delete-or-archive choice for a product (opened from Produits). */
export function DeleteProductModal({ productToDelete, deletingProduct, error, setProductToDelete, setError, handleConfirmDeleteProduct }: Props) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const cancelRef = useRef<HTMLButtonElement | null>(null);
  useModalFocus(dialogRef, Boolean(productToDelete), cancelRef, 50); // z-50
  if (!productToDelete) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-product-title"
        tabIndex={-1}
        className="bg-white text-[#202923] rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl border-2 border-[#D4AF62]"
      >
        <div className="px-6 py-4 bg-[#063D2E] text-white flex items-center justify-between border-b border-[#D4AF62]/40">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-[#D4AF62]" />
            <div>
              <h3 id="delete-product-title" className="text-base font-serif font-bold text-[#D4AF62]">
                Suppression / Archivage du Produit
              </h3>
              <p className="text-[11px] text-[#E8D4A5]">Gestion du catalogue — Maison Mus Luxury</p>
            </div>
          </div>
          <button aria-label="Fermer"
            type="button"
            onClick={() => { setProductToDelete(null); setError(""); }}
            disabled={deletingProduct}
            className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-white font-bold flex items-center justify-center transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-5 text-xs">
          {error && (
            <div className="p-3 bg-red-100 border border-red-300 text-red-800 rounded-xl text-xs font-semibold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-800 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {/* Product info banner */}
          <div className="p-4 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30 flex items-center gap-4">
            <div className="w-16 h-16 rounded-xl bg-[#063D2E]/10 border border-[#D4AF62]/40 flex items-center justify-center overflow-hidden shrink-0">
              {productToDelete.main_image_url || productToDelete.image_url ? (
                <img
                  src={mediaUrl(productToDelete.main_image_url || productToDelete.image_url)}
                  alt=""
                  className="w-full h-full object-cover"
                />
              ) : (
                <ShoppingBag className="w-7 h-7 text-[#063D2E]/40" />
              )}
            </div>
            <div className="space-y-1">
              <span className="px-2 py-0.5 rounded-full bg-[#063D2E] text-[#D4AF62] text-[10px] font-mono font-bold">
                SKU: {productToDelete.sku}
              </span>
              <h4 className="text-base font-serif font-bold text-[#063D2E]">{productToDelete.name_fr}</h4>
              <div className="text-[11px] text-gray-600 flex gap-3 font-mono">
                <span>
                  Prix de vente: <strong>{Number(productToDelete.selling_price_dzd || 0).toLocaleString()} DA</strong>
                </span>
                <span>
                  Stock: <strong>{productToDelete.total_stock ?? 0} unités</strong>
                </span>
                <span>
                  Statut: <strong>{({ archived: "Archivé (hors vitrine)", published: "Publié (en vente)", draft: "Brouillon" } as Record<string, string>)[productToDelete.status] || productToDelete.status}</strong>
                </span>
              </div>
            </div>
          </div>

          <p className="text-gray-700 leading-relaxed font-semibold">
            Veuillez sélectionner l'action à exécuter pour cet article :
          </p>

          {/* Action buttons */}
          <div className="space-y-3">
            {/* Permanent Hard Delete */}
            <div className="p-3.5 rounded-xl border border-red-200 bg-red-50/70 space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <strong className="text-red-900 block font-bold text-xs">
                    Option 1 : Suppression Définitive de la Base
                  </strong>
                  <span className="text-[11px] text-red-700 leading-relaxed block mt-0.5">
                    Seulement pour un article jamais vendu ni acheté (créé par erreur). S'il a déjà été vendu
                    (en ligne ou en magasin) ou acheté à un fournisseur, il est archivé à la place : les factures,
                    rapports et comptes fournisseurs restent exacts. Aucune commande n'est jamais effacée.
                  </span>

                </div>
                <button
                  type="button"
                  disabled={deletingProduct}
                  onClick={() => handleConfirmDeleteProduct(true)}
                  className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-red-700 hover:bg-red-800 disabled:opacity-50 text-white font-extrabold whitespace-nowrap shadow-xs shrink-0"
                >
                  <Trash2 className="w-4 h-4 text-white" />
                  <span>{deletingProduct ? "Suppression..." : "Supprimer Définitivement"}</span>
                </button>
              </div>
            </div>

            {/* Safe Soft Archive */}
            <div className="p-3.5 rounded-xl border border-amber-200 bg-amber-50/70 space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <strong className="text-amber-900 block font-bold text-xs">
                    Option 2 : Archivage Sécurisé (Recommandé)
                  </strong>
                  <span className="text-[11px] text-amber-800 leading-relaxed block mt-0.5">
                    Masque le produit de la vitrine tout en préservant l'intégrité des factures et de la comptabilité. Vous pouvez le réactiver à tout moment.
                  </span>
                </div>
                <button
                  type="button"
                  disabled={deletingProduct}
                  onClick={() => handleConfirmDeleteProduct(false)}
                  className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-extrabold whitespace-nowrap shadow-xs shrink-0"
                >
                  <Archive className="w-4 h-4 text-white" />
                  <span>{deletingProduct ? "Archivage..." : "Archiver la Pièce"}</span>
                </button>
              </div>
            </div>
          </div>

          <div className="flex justify-end pt-2 border-t border-gray-100">
            <button
              ref={cancelRef}
              type="button"
              disabled={deletingProduct}
              onClick={() => { setProductToDelete(null); setError(""); }}
              className="px-5 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold"
            >
              Annuler
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
