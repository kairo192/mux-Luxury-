import React, { useEffect, useState } from "react";
import { DesktopCmsApi } from "../api/adminClient";
import { notifyClientError, notifyClientSuccess, notifyClientWarning } from "../utils/clientNotifier";
import {
  PackageCheck,
  Building2,
  Plus,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Download,
  CreditCard,
  Trash2,
  X,
  Sparkles,
} from "lucide-react";

export function PurchasesPage({ onInventoryUpdated }: { onInventoryUpdated?: () => void }) {
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [purchases, setPurchases] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // New Supplier Form State
  const [supName, setSupName] = useState("");
  const [supCompany, setSupCompany] = useState("");
  const [supContact, setSupContact] = useState("");
  const [supPhone, setSupPhone] = useState("");
  const [supEmail, setSupEmail] = useState("");
  const [supAddress, setSupAddress] = useState("");
  const [supTaxId, setSupTaxId] = useState("");
  const [supNotes, setSupNotes] = useState("");

  // Edit Supplier Form State
  const [editingSupplier, setEditingSupplier] = useState<any | null>(null);
  const [supplierToDelete, setSupplierToDelete] = useState<{ id: number; name: string } | null>(null);
  const [deletingSupplier, setDeletingSupplier] = useState(false);
  const [poToReceive, setPoToReceive] = useState<any | null>(null);
  const [receivingPo, setReceivingPo] = useState(false);

  // New Purchase Order Form State
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | "">("");
  const [shippingCost, setShippingCost] = useState(0);
  const [taxCost, setTaxCost] = useState(0);
  const [expectedDate, setExpectedDate] = useState("");
  const [poNotes, setPoNotes] = useState("");
  const [orderItems, setOrderItems] = useState<Array<{
    product_id: number;
    variant_id?: number;
    product_name: string;
    variant_title: string;
    quantity: number;
    unit_cost_dzd: number;
  }>>([]);

  // Line item selector state
  const [selectedProdId, setSelectedProdId] = useState<number | "">("");
  const [selectedVariantId, setSelectedVariantId] = useState<number | "">("");
  const [lineQty, setLineQty] = useState(10);
  const [lineCost, setLineCost] = useState(2500);

  async function loadData() {
    setLoading(true);
    setError("");
    try {
      const [supRes, poRes, prodRes] = await Promise.all([
        DesktopCmsApi.listSuppliers(),
        DesktopCmsApi.listPurchases(),
        DesktopCmsApi.listAdminProducts({ include_archived: false }),
      ]);
      setSuppliers(supRes.items || []);
      setPurchases(poRes.items || []);
      setProducts(prodRes.items || []);
      if (!selectedSupplierId && (supRes.items || []).length > 0) {
        setSelectedSupplierId(supRes.items[0].id);
      }
      if (!selectedProdId && (prodRes.items || []).length > 0) {
        setSelectedProdId(prodRes.items[0].id);
        setLineCost(prodRes.items[0].purchase_cost_dzd || 2500);
      }
    } catch (err: any) {
      const tr = notifyClientError(err, "Erreur chargement des achats");
      setError(tr.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  // Update line cost default when product changes
  function handleProductSelect(prodId: number) {
    setSelectedProdId(prodId);
    const p = products.find((x) => x.id === prodId);
    if (p) {
      setLineCost(p.purchase_cost_dzd || 2500);
      if (p.variants && p.variants.length > 0) {
        setSelectedVariantId(p.variants[0].id);
      } else {
        setSelectedVariantId("");
      }
    }
  }

  function addItemToPurchaseOrder() {
    if (!selectedProdId) {
      notifyClientWarning("Sélection requise", "Veuillez choisir un produit à commander.");
      return;
    }
    const p = products.find((x) => x.id === Number(selectedProdId));
    if (!p) return;
    const v = (p.variants || []).find((x: any) => x.id === Number(selectedVariantId));

    setOrderItems((prev) => [
      ...prev,
      {
        product_id: p.id,
        variant_id: v ? v.id : undefined,
        product_name: p.name_fr,
        variant_title: v ? v.title : "Standard",
        quantity: Number(lineQty),
        unit_cost_dzd: Number(lineCost),
      },
    ]);
    notifyClientSuccess("Article ajouté", `${p.name_fr} (${lineQty} unités) ajouté au bon d'achat.`);
  }

  function removeOrderItem(index: number) {
    setOrderItems((prev) => prev.filter((_, i) => i !== index));
  }

  const itemsSubtotal = orderItems.reduce((acc, it) => acc + it.quantity * it.unit_cost_dzd, 0);
  const totalPurchaseCost = itemsSubtotal + Number(shippingCost) + Number(taxCost);

  async function handleCreatePurchaseOrder(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedSupplierId) {
      notifyClientWarning("Fournisseur requis", "Veuillez sélectionner un fournisseur.");
      return;
    }
    if (orderItems.length === 0) {
      notifyClientWarning("Articles requis", "Ajoutez au moins un article dans le bon de commande.");
      return;
    }
    setError("");
    try {
      const res = await DesktopCmsApi.createPurchaseOrder({
        supplier_id: Number(selectedSupplierId),
        shipping_dzd: Number(shippingCost),
        tax_dzd: Number(taxCost),
        expected_date: expectedDate || undefined,
        notes: poNotes.trim() || undefined,
        items: orderItems.map((it) => ({
          product_id: it.product_id,
          variant_id: it.variant_id,
          quantity: it.quantity,
          unit_cost_dzd: it.unit_cost_dzd,
        })),
      });
      notifyClientSuccess("Bon de commande créé", `Bon de commande ${res.reference} enregistré (${res.total_cost_dzd} DA).`);
      setOrderItems([]);
      setShippingCost(0);
      setTaxCost(0);
      setPoNotes("");
      await loadData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Création du bon de commande impossible");
      setError(tr.message);
    }
  }

  async function confirmReceivePo() {
    if (!poToReceive) return;
    setReceivingPo(true);
    setError("");
    try {
      await DesktopCmsApi.receivePurchaseOrder(poToReceive.id);
      notifyClientSuccess("Réception confirmée", `Bon ${poToReceive.reference} réceptionné en stock avec succès.`);
      setPoToReceive(null);
      await loadData();
      if (onInventoryUpdated) onInventoryUpdated();
    } catch (err: any) {
      const tr = notifyClientError(err, "Réception impossible");
      setError(tr.message);
    } finally {
      setReceivingPo(false);
    }
  }

  async function handlePayPurchaseOrder(poId: number, ref: string, amount: number) {
    const method = window.prompt(`Régler le fournisseur pour le bon ${ref} (${amount} DA).\nMode de paiement : tapez 'cash' (Caisse) ou 'bank_transfer' (Banque) :`, "cash");
    if (!method) return;
    const cleanMethod = method.trim().toLowerCase() === "bank_transfer" ? "bank_transfer" : "cash";

    setError("");
    try {
      await DesktopCmsApi.payPurchaseOrder(poId, cleanMethod);
      notifyClientSuccess("Règlement effectué", `Paiement de ${amount} DA enregistré via ${cleanMethod === "cash" ? "Caisse" : "Banque"}.`);
      await loadData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Règlement impossible");
      setError(tr.message);
    }
  }

  async function handleCreateSupplier(e: React.FormEvent) {
    e.preventDefault();
    if (!supName.trim()) return;
    setError("");
    try {
      await DesktopCmsApi.createSupplier({
        name: supName.trim(),
        company_name: supCompany.trim() || undefined,
        contact_person: supContact.trim() || undefined,
        phone: supPhone.trim() || undefined,
        email: supEmail.trim() || undefined,
        address: supAddress.trim() || undefined,
        tax_id: supTaxId.trim() || undefined,
        notes: supNotes.trim() || undefined,
      });
      notifyClientSuccess("Fournisseur créé", `Fournisseur "${supName}" ajouté avec succès.`);
      setSupName("");
      setSupCompany("");
      setSupContact("");
      setSupPhone("");
      setSupEmail("");
      setSupAddress("");
      setSupTaxId("");
      setSupNotes("");
      await loadData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Création du fournisseur impossible");
      setError(tr.message);
    }
  }

  async function handleSaveEditedSupplier(e: React.FormEvent) {
    e.preventDefault();
    if (!editingSupplier) return;
    setError("");
    try {
      await DesktopCmsApi.updateSupplier(editingSupplier.id, {
        name: editingSupplier.name,
        company_name: editingSupplier.company_name,
        contact_person: editingSupplier.contact_person,
        phone: editingSupplier.phone,
        email: editingSupplier.email,
        address: editingSupplier.address,
        tax_id: editingSupplier.tax_id,
        notes: editingSupplier.notes,
      });
      notifyClientSuccess("Fournisseur mis à jour", `Coordonnées de "${editingSupplier.name}" enregistrées.`);
      setEditingSupplier(null);
      await loadData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Modification du fournisseur impossible");
      setError(tr.message);
    }
  }

  async function confirmDeleteSupplier() {
    if (!supplierToDelete) return;
    setDeletingSupplier(true);
    setError("");
    try {
      await DesktopCmsApi.deleteSupplier(supplierToDelete.id);
      notifyClientSuccess("Fournisseur retiré", `Fournisseur "${supplierToDelete.name}" supprimé/archivé.`);
      setSupplierToDelete(null);
      await loadData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Suppression impossible");
      setError(tr.message);
    } finally {
      setDeletingSupplier(false);
    }
  }

  return (
    <div className="space-y-6 text-xs">
      {/* Header Info Banner */}
      <div className="bg-white p-5 rounded-2xl border border-[#D4AF62]/40 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-serif font-bold text-[#063D2E]">
            Gestion des Achats &amp; Fournisseurs (ERP Approvisionnements)
          </h2>
          <p className="text-gray-500">
            Contrôlez les coûts d'achat, les réceptions en stock avec calcul du Coût Moyen Pondéré (PMP) et les dettes fournisseurs.
          </p>
        </div>
        <button
          type="button"
          onClick={loadData}
          className="px-4 py-2 rounded-xl bg-[#F8F6F0] text-[#063D2E] border border-[#D4AF62]/40 font-bold hover:bg-[#D4AF62]/20"
        >
          Actualiser les données
        </button>
      </div>

      {error && <div className="p-3 rounded-xl bg-red-100 text-red-900 font-bold">{error}</div>}
      {successMsg && <div className="p-3 rounded-xl bg-emerald-100 text-emerald-900 font-bold">{successMsg}</div>}

      {/* Grid: Create Purchase Order & Register Supplier */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Create Purchase Order (2 Cols) */}
        <div className="lg:col-span-2 space-y-4">
          <form onSubmit={handleCreatePurchaseOrder} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4">
            <h3 className="text-base font-serif font-bold text-[#063D2E] border-b pb-2">
              + Émettre un Bon de Commande Fournisseur (Approvisionnement)
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block font-bold mb-1">Fournisseur *</label>
                <select
                  value={selectedSupplierId}
                  onChange={(e) => setSelectedSupplierId(Number(e.target.value))}
                  required
                  className="w-full px-3 py-2 border rounded-xl bg-white font-semibold"
                >
                  <option value="">-- Choisir un fournisseur --</option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} {s.company_name ? `(${s.company_name})` : ""} - Dette: {s.balance_dzd} DA
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-bold mb-1">Frais de transport / expédition (DA)</label>
                <input
                  type="number"
                  min={0}
                  value={shippingCost}
                  onChange={(e) => setShippingCost(Number(e.target.value))}
                  className="w-full px-3 py-2 border rounded-xl bg-white font-bold"
                />
              </div>

              <div>
                <label className="block font-bold mb-1">Date d'arrivée prévue</label>
                <input
                  type="date"
                  value={expectedDate}
                  onChange={(e) => setExpectedDate(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl bg-white"
                />
              </div>
            </div>

            {/* Line Item Adder */}
            <div className="p-4 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30 space-y-3">
              <span className="font-bold text-[#063D2E] block">Ajouter des articles à commander :</span>
              <div className="grid grid-cols-1 md:grid-cols-5 gap-2 items-end">
                <div className="md:col-span-2">
                  <label className="block font-semibold mb-1">Produit du catalogue</label>
                  <select
                    value={selectedProdId}
                    onChange={(e) => handleProductSelect(Number(e.target.value))}
                    className="w-full px-3 py-2 border rounded-xl bg-white font-semibold"
                  >
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name_fr} ({p.sku})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-semibold mb-1">Quantité (unités)</label>
                  <input
                    type="number"
                    min={1}
                    value={lineQty}
                    onChange={(e) => setLineQty(Number(e.target.value))}
                    className="w-full px-3 py-2 border rounded-xl bg-white font-bold"
                  />
                </div>

                <div>
                  <label className="block font-semibold mb-1">Coût d'achat unit. (DA)</label>
                  <input
                    type="number"
                    min={0}
                    value={lineCost}
                    onChange={(e) => setLineCost(Number(e.target.value))}
                    className="w-full px-3 py-2 border rounded-xl bg-white font-bold"
                  />
                </div>

                <div>
                  <button
                    type="button"
                    onClick={addItemToPurchaseOrder}
                    className="w-full py-2 px-3 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold shadow"
                  >
                    + Ajouter
                  </button>
                </div>
              </div>

              {/* Items List inside draft PO */}
              {orderItems.length > 0 ? (
                <div className="mt-3 border rounded-xl bg-white divide-y">
                  {orderItems.map((it, idx) => (
                    <div key={idx} className="p-2.5 flex items-center justify-between">
                      <div>
                        <span className="font-bold text-[#063D2E]">{it.product_name}</span>{" "}
                        <span className="text-gray-500 font-mono text-[11px]">({it.variant_title})</span>
                        <div className="text-[11px] text-gray-600">
                          {it.quantity} unités × {it.unit_cost_dzd} DA = <strong>{it.quantity * it.unit_cost_dzd} DA</strong>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeOrderItem(idx)}
                        className="inline-flex items-center gap-1 text-red-600 font-bold px-2 py-1 hover:underline"
                      >
                        <X className="w-3.5 h-3.5" />
                        <span>Retirer</span>
                      </button>
                    </div>
                  ))}
                  <div className="p-3 bg-[#063D2E]/5 font-bold flex justify-between items-center text-sm">
                    <span>Total Sous-Total Marchandises :</span>
                    <span className="text-[#063D2E] font-extrabold">{itemsSubtotal} DA</span>
                  </div>
                </div>
              ) : (
                <p className="text-gray-400 italic text-[11px]">Aucun article sélectionné pour l'instant.</p>
              )}
            </div>

            {/* Total Summary & Submit */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t">
              <div>
                <span className="text-gray-500">Coût Total d'Acquisition (Marchandises + Transport) :</span>
                <p className="text-xl font-extrabold text-[#063D2E]">{totalPurchaseCost} DA</p>
              </div>
              <button
                type="submit"
                className="px-6 py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold shadow hover:bg-[#D4AF62]/90"
              >
                Enregistrer &amp; Valider le Bon d'Achat
              </button>
            </div>
          </form>
        </div>

        {/* Right: Supplier Management (1 Col) */}
        <div className="space-y-4">
          <form onSubmit={handleCreateSupplier} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
            <h3 className="text-base font-serif font-bold text-[#063D2E] border-b pb-2">
              + Ajouter un Fournisseur
            </h3>
            <div>
              <label className="block font-bold mb-1">Nom du fournisseur *</label>
              <input
                value={supName}
                onChange={(e) => setSupName(e.target.value)}
                required
                placeholder="ex: Parfumerie d'Alger Import"
                className="w-full px-3 py-2 border rounded-xl"
              />
            </div>
            <div>
              <label className="block font-bold mb-1">Raison Sociale / Société</label>
              <input
                value={supCompany}
                onChange={(e) => setSupCompany(e.target.value)}
                placeholder="SARL Luxe Import"
                className="w-full px-3 py-2 border rounded-xl"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block font-bold mb-1">Téléphone</label>
                <input
                  value={supPhone}
                  onChange={(e) => setSupPhone(e.target.value)}
                  placeholder="0550..."
                  className="w-full px-3 py-2 border rounded-xl"
                />
              </div>
              <div>
                <label className="block font-bold mb-1">Contact</label>
                <input
                  value={supContact}
                  onChange={(e) => setSupContact(e.target.value)}
                  placeholder="Mohamed"
                  className="w-full px-3 py-2 border rounded-xl"
                />
              </div>
            </div>
            <div>
              <label className="block font-bold mb-1">Adresse / Wilaya</label>
              <input
                value={supAddress}
                onChange={(e) => setSupAddress(e.target.value)}
                placeholder="Alger, Blida..."
                className="w-full px-3 py-2 border rounded-xl"
              />
            </div>
            <button
              type="submit"
              className="w-full py-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold shadow hover:bg-[#02291F]"
            >
              Enregistrer le Fournisseur
            </button>
          </form>

          {/* Quick Suppliers Directory */}
          <div className="bg-white p-5 rounded-2xl border border-[#D4AF62]/40 space-y-3 max-h-96 overflow-y-auto">
            <h4 className="font-bold text-[#063D2E] border-b pb-1">
              Répertoire Fournisseurs ({suppliers.length})
            </h4>
            {suppliers.map((s) => (
              <div key={s.id} className="p-3 rounded-xl border border-gray-200 space-y-1 hover:border-[#D4AF62]/50">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-[#063D2E]">{s.name}</span>
                  <span className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] ${
                    s.balance_dzd > 0 ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-900"
                  }`}>
                    Dette: {s.balance_dzd} DA
                  </span>
                </div>
                <div className="text-[11px] text-gray-500">
                  {s.phone && <span>Tél: {s.phone} • </span>}
                  {s.address && <span>{s.address}</span>}
                </div>
                <div className="flex justify-end gap-2 pt-1 border-t text-[10px]">
                  <button
                    type="button"
                    onClick={() => setEditingSupplier(s)}
                    className="text-[#063D2E] font-bold hover:underline"
                  >
                    Modifier
                  </button>
                  <button
                    type="button"
                    onClick={() => setSupplierToDelete({ id: s.id, name: s.name })}
                    className="text-red-600 font-bold hover:underline"
                  >
                    Supprimer
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Edit Supplier Modal */}
      {editingSupplier && (
        <form onSubmit={handleSaveEditedSupplier} className="bg-[#F8F6F0] p-6 rounded-2xl border-2 border-[#D4AF62] space-y-3">
          <div className="flex justify-between items-center border-b pb-2">
            <h4 className="text-base font-serif font-bold text-[#063D2E]">
              Modifier Fournisseur #{editingSupplier.id} : {editingSupplier.name}
            </h4>
            <button
              type="button"
              onClick={() => setEditingSupplier(null)}
              className="p-1 rounded-lg text-gray-500 hover:text-black transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block font-bold mb-1">Nom *</label>
              <input
                value={editingSupplier.name || ""}
                onChange={(e) => setEditingSupplier({ ...editingSupplier, name: e.target.value })}
                required
                className="w-full px-3 py-2 border rounded-xl bg-white"
              />
            </div>
            <div>
              <label className="block font-bold mb-1">Société</label>
              <input
                value={editingSupplier.company_name || ""}
                onChange={(e) => setEditingSupplier({ ...editingSupplier, company_name: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl bg-white"
              />
            </div>
            <div>
              <label className="block font-bold mb-1">Téléphone</label>
              <input
                value={editingSupplier.phone || ""}
                onChange={(e) => setEditingSupplier({ ...editingSupplier, phone: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl bg-white"
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setEditingSupplier(null)} className="px-4 py-2 rounded-xl bg-gray-200 font-bold">Annuler</button>
            <button type="submit" className="px-5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold">Enregistrer</button>
          </div>
        </form>
      )}

      {/* Historical Purchase Orders List */}
      <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4">
        <h3 className="text-base font-serif font-bold text-[#063D2E]">
          Historique des Bons de Commande &amp; Réceptions Stock ({purchases.length})
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#063D2E] text-[#E8D4A5]">
                <th className="p-3">Réf / Date</th>
                <th className="p-3">Fournisseur</th>
                <th className="p-3">Articles commandés</th>
                <th className="p-3">Coût Total (DA)</th>
                <th className="p-3">Statut Réception</th>
                <th className="p-3">Paiement Dette</th>
                <th className="p-3 text-right">Actions ERP</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {purchases.map((po) => (
                <tr key={po.id} className="hover:bg-gray-50">
                  <td className="p-3">
                    <span className="font-mono font-bold text-[#063D2E] block">{po.reference}</span>
                    <span className="text-[11px] text-gray-500">{po.created_at?.slice(0, 10)}</span>
                  </td>
                  <td className="p-3 font-semibold">
                    {po.supplier_name}
                    {po.supplier_phone && <span className="block text-[11px] text-gray-500">{po.supplier_phone}</span>}
                  </td>
                  <td className="p-3">
                    <div className="space-y-0.5">
                      {(po.items || []).map((it: any) => (
                        <div key={it.id} className="text-[11px]">
                          <strong>{it.quantity_ordered}×</strong> {it.product_name} ({it.variant_title})
                        </div>
                      ))}
                    </div>
                  </td>
                  <td className="p-3 font-extrabold text-[#063D2E] text-sm">
                    {po.total_cost_dzd} DA
                  </td>
                  <td className="p-3">
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-bold text-[10px] ${
                      po.status === "received" ? "bg-emerald-100 text-emerald-900" : "bg-amber-100 text-amber-900"
                    }`}>
                      {po.status === "received" ? (
                        <>
                          <CheckCircle2 className="w-3 h-3 text-emerald-700" />
                          <span>Réceptionné en stock</span>
                        </>
                      ) : (
                        <>
                          <Clock className="w-3 h-3 text-amber-700" />
                          <span>En attente de livraison</span>
                        </>
                      )}
                    </span>
                  </td>
                  <td className="p-3">
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-bold text-[10px] ${
                      po.payment_status === "paid" ? "bg-emerald-100 text-emerald-900" : "bg-red-100 text-red-900"
                    }`}>
                      {po.payment_status === "paid" ? (
                        <>
                          <CheckCircle2 className="w-3 h-3 text-emerald-700" />
                          <span>Payé</span>
                        </>
                      ) : (
                        <span>Dû ({po.total_cost_dzd - (po.paid_amount_dzd || 0)} DA)</span>
                      )}
                    </span>
                  </td>
                  <td className="p-3 text-right space-x-2">
                    {po.status !== "received" && (
                      <button
                        type="button"
                        onClick={() => setPoToReceive(po)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold shadow hover:bg-[#02291F] transition active:scale-95"
                      >
                        <Download className="w-3.5 h-3.5 text-[#D4AF62]" />
                        <span>Réceptionner</span>
                      </button>
                    )}
                    {po.payment_status !== "paid" && (
                      <button
                        type="button"
                        onClick={() => handlePayPurchaseOrder(po.id, po.reference, po.total_cost_dzd - (po.paid_amount_dzd || 0))}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#D4AF62] text-[#02291F] font-bold shadow hover:bg-[#D4AF62]/90"
                      >
                        <CreditCard className="w-3.5 h-3.5 text-[#02291F]" />
                        <span>Régler</span>
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {/* Modal: Confirm PO Receipt */}
      {poToReceive && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeInBackdrop">
          <div className="bg-[#F8F6F0] rounded-3xl border border-[#D4AF62]/50 shadow-2xl max-w-md w-full overflow-hidden animate-scaleInModal">
            <div className="bg-gradient-to-r from-[#011C15] via-[#063D2E] to-[#02291F] px-6 py-4 flex items-center justify-between border-b border-[#D4AF62]/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-300">
                  <Download className="w-4 h-4 text-emerald-300" />
                </div>
                <div>
                  <h3 className="text-base font-serif font-bold text-white tracking-wide">
                    Réception en Stock
                  </h3>
                  <p className="text-[11px] text-[#E8D4A5]/80">Bon d'Approvisionnement : {poToReceive.reference}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setPoToReceive(null)}
                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-[#E8D4A5] flex items-center justify-center transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 space-y-4 text-xs">
              <p className="text-gray-700 leading-relaxed">
                Confirmez-vous la réception physique en stock de la marchandise pour ce bon de commande ?
              </p>
              <div className="p-3.5 rounded-2xl bg-white border border-[#D4AF62]/40 space-y-1.5">
                <div className="flex justify-between text-gray-600">
                  <span>Référence :</span>
                  <span className="font-mono font-bold text-[#063D2E]">{poToReceive.reference}</span>
                </div>
                <div className="flex justify-between text-gray-600">
                  <span>Montant Total :</span>
                  <span className="font-mono font-bold text-[#063D2E]">{Number(poToReceive.total_cost_dzd || 0).toLocaleString()} DA</span>
                </div>
              </div>
              <p className="text-[11px] text-emerald-800 bg-emerald-50 p-2.5 rounded-xl border border-emerald-200 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-emerald-700 shrink-0" />
                <span>Cette action incrémentera automatiquement les stocks des variantes et mettra à jour le coût moyen d'achat pondéré.</span>
              </p>
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setPoToReceive(null)}
                  disabled={receivingPo}
                  className="px-4 py-2 rounded-xl bg-gray-200 hover:bg-gray-300 text-gray-700 font-bold transition"
                >
                  Annuler
                </button>
                <button
                  type="button"
                  onClick={confirmReceivePo}
                  disabled={receivingPo}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-[#063D2E] to-[#0A5C45] hover:from-[#02291F] hover:to-[#063D2E] text-[#D4AF62] font-bold shadow-md transition disabled:opacity-50"
                >
                  {receivingPo ? "Réception en cours..." : "Confirmer la Réception"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Confirm Supplier Deletion */}
      {supplierToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeInBackdrop">
          <div className="bg-[#F8F6F0] rounded-3xl border border-[#D4AF62]/50 shadow-2xl max-w-md w-full overflow-hidden animate-scaleInModal">
            <div className="bg-gradient-to-r from-[#011C15] via-[#063D2E] to-[#02291F] px-6 py-4 flex items-center justify-between border-b border-[#D4AF62]/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-red-500/20 text-red-300">
                  <Building2 className="w-4 h-4 text-red-300" />
                </div>
                <div>
                  <h3 className="text-base font-serif font-bold text-white tracking-wide">
                    Retirer le Fournisseur
                  </h3>
                  <p className="text-[11px] text-[#E8D4A5]/80">Suppression ou Archivage</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSupplierToDelete(null)}
                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-[#E8D4A5] flex items-center justify-center transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 space-y-4 text-xs">
              <p className="text-gray-700 leading-relaxed">
                Êtes-vous certain de vouloir supprimer ou archiver le fournisseur suivant ?
              </p>
              <div className="p-3.5 rounded-2xl bg-white border border-[#D4AF62]/40">
                <div className="font-bold text-[#063D2E] text-sm">{supplierToDelete.name}</div>
                <div className="text-[11px] text-gray-500 mt-1">Identifiant #{supplierToDelete.id}</div>
              </div>
              <p className="text-[11px] text-amber-800 bg-amber-50 p-2.5 rounded-xl border border-amber-200 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
                <span>Si ce fournisseur a des bons de commandes historiques, il sera archivé afin de préserver l'intégrité de vos factures et de votre comptabilité.</span>
              </p>
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setSupplierToDelete(null)}
                  disabled={deletingSupplier}
                  className="px-4 py-2 rounded-xl bg-gray-200 hover:bg-gray-300 text-gray-700 font-bold transition"
                >
                  Annuler
                </button>
                <button
                  type="button"
                  onClick={confirmDeleteSupplier}
                  disabled={deletingSupplier}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white font-bold shadow-md transition disabled:opacity-50"
                >
                  {deletingSupplier ? "Traitement..." : "Confirmer le Retrait"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

