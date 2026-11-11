import React, { useEffect, useState } from "react";
import { DesktopCmsApi } from "../api/adminClient";
import { notifyClientError, notifyClientSuccess, notifyClientWarning, confirmClientAction } from "../utils/clientNotifier";
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
  Tag,
} from "lucide-react";
import {
  isLabelPrinterConfigured,
  loadLabelPrinterSettings,
  printLabels,
  isTauriRuntime,
  type LabelPayload,
} from "../utils/posHardware";
import { useT } from "../i18n";

export function PurchasesPage({ onInventoryUpdated }: { onInventoryUpdated?: () => void }) {
  const t = useT();
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
  const [lineQty, setLineQty] = useState(1);
  const [lineCost, setLineCost] = useState(0);

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
      setLineCost(p.purchase_cost_dzd || 0);
      // One variant: it is the one. Several: the user must choose.
      if (p.variants && p.variants.length === 1) {
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
    if (!v && (p.variants || []).length !== 1) {
      notifyClientWarning("Variante requise", `Choisissez la couleur / taille de « ${p.name_fr} » à commander.`);
      return;
    }
    if (!(Number(lineQty) > 0) || !(Number(lineCost) > 0)) {
      notifyClientWarning("Quantité et coût requis", "Indiquez la quantité commandée et le coût d'achat unitaire en DA.");
      return;
    }

    setOrderItems((prev) => [
      ...prev,
      {
        product_id: p.id,
        variant_id: v ? v.id : undefined,
        product_name: p.name_fr,
        variant_title: v ? v.title : (p.variants?.[0]?.title || ""),
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
      // Ask the operator whether to print labels now; keep the receive modal
      // in a second-step state instead of closing immediately so the batch
      // print is one more click away, with zero guesswork.
      await offerToPrintLabels(poToReceive.id, poToReceive.reference);
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

  async function offerToPrintLabels(poId: number, reference: string) {
    if (!isTauriRuntime() || !isLabelPrinterConfigured()) {
      // No label printer configured → nothing to offer. The operator can
      // still print per-variant labels from the Products page later.
      return;
    }
    try {
      const batch = await DesktopCmsApi.getPurchaseOrderLabels(poId);
      const printable = (batch.labels || []).filter((l: any) => l.barcode_value);
      const missing = (batch.variants_without_barcode || 0) as number;
      const totalCopies = printable.reduce((n: number, l: any) => n + (l.copies || 0), 0);
      if (!printable.length) {
        notifyClientWarning(
          "Impression impossible",
          missing > 0
            ? `${missing} article(s) de ce bon n'ont pas de code-barres. Assignez-leur un code dans Produits avant d'imprimer les étiquettes.`
            : "Aucune étiquette à imprimer pour ce bon.",
        );
        return;
      }
      const confirmMsg = missing > 0
        ? `Imprimer ${totalCopies} étiquettes maintenant ?\n(${missing} article(s) sans code-barres seront ignorés — à assigner dans Produits.)`
        : `Imprimer ${totalCopies} étiquettes pour le bon ${reference} ?`;
      const confirmed = await confirmClientAction({
        title: "Impression d'étiquettes",
        message: confirmMsg,
        danger: false,
      });
      if (!confirmed) return;
      const labels: LabelPayload[] = printable.map((l: any) => ({
        header: l.header,
        product_name: l.product_name,
        variant_title: l.variant_title,
        sku: l.sku,
        price_text: l.price_text,
        barcode_value: l.barcode_value,
        barcode_kind: l.barcode_kind === "ean13" ? "ean13" : "code128",
        copies: Math.max(1, Math.min(100, Number(l.copies) || 1)),
      }));
      const r = await printLabels(loadLabelPrinterSettings(), labels);
      if (r.ok) {
        notifyClientSuccess("Étiquettes envoyées", `${totalCopies} étiquettes transmises à l'étiqueteuse.`);
      } else {
        notifyClientError({ userMessage: r.error }, "Impression des étiquettes impossible");
      }
    } catch (err) {
      notifyClientError(err, "Impression des étiquettes impossible");
    }
  }

  async function handlePayPurchaseOrder(poId: number, ref: string, amount: number) {
    // Button-based choice replaces the old window.prompt — far friendlier on a
    // touchscreen and leaves no room for typos ("cach", "bank transfer", …)
    // that would silently fall through to the default method.
    setPayDialog({ poId, ref, amount });
  }

  const [payDialog, setPayDialog] = useState<null | { poId: number; ref: string; amount: number }>(null);
  const confirmPayment = async (method: "cash" | "bank_transfer") => {
    if (!payDialog) return;
    const { poId, ref, amount } = payDialog;
    setPayDialog(null);
    setError("");
    try {
      await DesktopCmsApi.payPurchaseOrder(poId, method);
      notifyClientSuccess(
        "Règlement effectué",
        `Paiement de ${amount} DA pour le bon ${ref} enregistré via ${method === "cash" ? "Caisse" : "Banque"}.`,
      );
      await loadData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Règlement impossible");
      setError(tr.message);
    }
  };

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
            {t("purchases.title")}
          </h2>
          <p className="text-gray-500">
            {t("purchases.subtitle")}
          </p>
        </div>
        <button
          type="button"
          onClick={loadData}
          className="px-4 py-2 rounded-xl bg-[#F8F6F0] text-[#063D2E] border border-[#D4AF62]/40 font-bold hover:bg-[#D4AF62]/20"
        >
          {t("common.refresh")}
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
              {t("purchases.create_po_title")}
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block font-bold mb-1">{t("purchases.supplier_label")}</label>
                <select
                  value={selectedSupplierId}
                  onChange={(e) => setSelectedSupplierId(Number(e.target.value))}
                  required
                  className="w-full px-3 py-2 border rounded-xl bg-white font-semibold"
                >
                  <option value="">{t("purchases.supplier_placeholder")}</option>
                  {suppliers.filter((s) => s.is_active !== 0 && s.is_active !== false).map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} {s.company_name ? `(${s.company_name})` : ""} - {t("purchases.debt", { amount: s.balance_dzd })}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-bold mb-1">{t("purchases.shipping_cost")}</label>
                <input
                  type="number"
                  min={0}
                  value={shippingCost}
                  onChange={(e) => setShippingCost(Number(e.target.value))}
                  className="w-full px-3 py-2 border rounded-xl bg-white font-bold"
                />
              </div>

              <div>
                <label className="block font-bold mb-1">{t("purchases.expected_date")}</label>
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
              <span className="font-bold text-[#063D2E] block">{t("purchases.add_items_label")}</span>
              <div className="grid grid-cols-1 md:grid-cols-5 gap-2 items-end">
                <div className="md:col-span-2">
                  <label className="block font-semibold mb-1">{t("purchases.catalog_product")}</label>
                  <select
                    value={selectedProdId}
                    onChange={(e) => handleProductSelect(Number(e.target.value))}
                    className="w-full px-3 py-2 border rounded-xl bg-white font-semibold"
                  >
                    <option value="">— Choisir un produit —</option>
                    {products.filter((p) => p.status !== "archived" && !p.deleted_at).map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name_fr} ({p.sku})
                      </option>
                    ))}
                  </select>
                  {(() => {
                    const sel = products.find((x) => x.id === Number(selectedProdId));
                    const vs = sel?.variants || [];
                    if (vs.length < 2) return null;
                    return (
                      <select
                        aria-label="Variante"
                        value={selectedVariantId}
                        onChange={(e) => setSelectedVariantId(e.target.value ? Number(e.target.value) : "")}
                        className="mt-2 w-full px-3 py-2 border-2 border-[#D4AF62] rounded-xl bg-white font-semibold"
                      >
                        <option value="">— Variante (couleur / taille) —</option>
                        {vs.map((v: any) => (
                          <option key={v.id} value={v.id}>
                            {v.title} · {v.sku} · stock {v.stock_qty}
                          </option>
                        ))}
                      </select>
                    );
                  })()}
                </div>

                <div>
                  <label className="block font-semibold mb-1">{t("purchases.quantity_units")}</label>
                  <input
                    type="number"
                    min={1}
                    value={lineQty}
                    onChange={(e) => setLineQty(Number(e.target.value))}
                    className="w-full px-3 py-2 border rounded-xl bg-white font-bold"
                  />
                </div>

                <div>
                  <label className="block font-semibold mb-1">{t("purchases.unit_cost")}</label>
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
                    {t("purchases.btn_add")}
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
                        <span>{t("purchases.btn_remove")}</span>
                      </button>
                    </div>
                  ))}
                  <div className="p-3 bg-[#063D2E]/5 font-bold flex justify-between items-center text-sm">
                    <span>{t("purchases.items_subtotal")}</span>
                    <span className="text-[#063D2E] font-extrabold">{itemsSubtotal} DA</span>
                  </div>
                </div>
              ) : (
                <p className="text-gray-400 italic text-[11px]">{t("purchases.no_items")}</p>
              )}
            </div>

            {/* Total Summary & Submit */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t">
              <div>
                <span className="text-gray-500">{t("purchases.total_acq_cost")}</span>
                <p className="text-xl font-extrabold text-[#063D2E]">{totalPurchaseCost} DA</p>
              </div>
              <button
                type="submit"
                className="px-6 py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold shadow hover:bg-[#D4AF62]/90"
              >
                {t("purchases.btn_submit_po")}
              </button>
            </div>
          </form>
        </div>

        {/* Right: Supplier Management (1 Col) */}
        <div className="space-y-4">
          <form onSubmit={handleCreateSupplier} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
            <h3 className="text-base font-serif font-bold text-[#063D2E] border-b pb-2">
              {t("purchases.add_supplier_title")}
            </h3>
            <div>
              <label className="block font-bold mb-1">{t("purchases.supplier_name")}</label>
              <input
                value={supName}
                onChange={(e) => setSupName(e.target.value)}
                required
                placeholder="ex: Parfumerie d'Alger Import"
                className="w-full px-3 py-2 border rounded-xl"
              />
            </div>
            <div>
              <label className="block font-bold mb-1">{t("purchases.company_name")}</label>
              <input
                value={supCompany}
                onChange={(e) => setSupCompany(e.target.value)}
                placeholder="SARL Luxe Import"
                className="w-full px-3 py-2 border rounded-xl"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block font-bold mb-1">{t("purchases.phone")}</label>
                <input
                  value={supPhone}
                  onChange={(e) => setSupPhone(e.target.value)}
                  placeholder="0550..."
                  className="w-full px-3 py-2 border rounded-xl"
                />
              </div>
              <div>
                <label className="block font-bold mb-1">{t("purchases.contact")}</label>
                <input
                  value={supContact}
                  onChange={(e) => setSupContact(e.target.value)}
                  placeholder="Mohamed"
                  className="w-full px-3 py-2 border rounded-xl"
                />
              </div>
            </div>
            <div>
              <label className="block font-bold mb-1">{t("purchases.address_wilaya")}</label>
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
              {t("purchases.save_supplier")}
            </button>
          </form>

          {/* Quick Suppliers Directory */}
          <div className="bg-white p-5 rounded-2xl border border-[#D4AF62]/40 space-y-3 max-h-96 overflow-y-auto">
            <h4 className="font-bold text-[#063D2E] border-b pb-1">
              {t("purchases.suppliers_dir", { count: suppliers.length })}
            </h4>
            {suppliers.map((s) => (
              <div key={s.id} className="p-3 rounded-xl border border-gray-200 space-y-1 hover:border-[#D4AF62]/50">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-[#063D2E]">
                    {s.name}
                    {(s.is_active === 0 || s.is_active === false) && (
                      <span className="ms-2 px-1.5 py-0.5 rounded bg-gray-200 text-gray-600 text-[10px] font-bold">Archivé</span>
                    )}
                  </span>
                  <span className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] ${
                    s.balance_dzd > 0 ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-900"
                  }`}>
                    {t("purchases.debt", { amount: s.balance_dzd })}
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
                    {t("common.edit")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setSupplierToDelete({ id: s.id, name: s.name })}
                    className="text-red-600 font-bold hover:underline"
                  >
                    {t("common.delete")}
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
              {t("purchases.edit_sup_title", { id: editingSupplier.id, name: editingSupplier.name })}
            </h4>
            <button aria-label="Fermer"
              type="button"
              onClick={() => setEditingSupplier(null)}
              className="p-1 rounded-lg text-gray-500 hover:text-black transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block font-bold mb-1">{t("purchases.supplier_name")}</label>
              <input
                value={editingSupplier.name || ""}
                onChange={(e) => setEditingSupplier({ ...editingSupplier, name: e.target.value })}
                required
                className="w-full px-3 py-2 border rounded-xl bg-white"
              />
            </div>
            <div>
              <label className="block font-bold mb-1">{t("purchases.company_name")}</label>
              <input
                value={editingSupplier.company_name || ""}
                onChange={(e) => setEditingSupplier({ ...editingSupplier, company_name: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl bg-white"
              />
            </div>
            <div>
              <label className="block font-bold mb-1">{t("purchases.phone")}</label>
              <input
                value={editingSupplier.phone || ""}
                onChange={(e) => setEditingSupplier({ ...editingSupplier, phone: e.target.value })}
                className="w-full px-3 py-2 border rounded-xl bg-white"
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setEditingSupplier(null)} className="px-4 py-2 rounded-xl bg-gray-200 font-bold">{t("common.cancel")}</button>
            <button type="submit" className="px-5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold">{t("common.save")}</button>
          </div>
        </form>
      )}

      {/* Historical Purchase Orders List */}
      <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4">
        <h3 className="text-base font-serif font-bold text-[#063D2E]">
          {t("purchases.history_title", { count: purchases.length })}
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-start border-collapse">
            <thead>
              <tr className="bg-[#063D2E] text-[#E8D4A5]">
                <th className="p-3 text-start">{t("purchases.th_ref_date")}</th>
                <th className="p-3 text-start">{t("purchases.th_supplier")}</th>
                <th className="p-3 text-start">{t("purchases.th_items")}</th>
                <th className="p-3 text-start">{t("purchases.th_total_cost")}</th>
                <th className="p-3 text-start">{t("purchases.th_status")}</th>
                <th className="p-3 text-start">{t("purchases.th_payment")}</th>
                <th className="p-3 text-end">{t("purchases.th_actions")}</th>
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
                          <span>{t("purchases.status_received")}</span>
                        </>
                      ) : (
                        <>
                          <Clock className="w-3 h-3 text-amber-700" />
                          <span>{t("purchases.status_pending")}</span>
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
                          <span>{t("purchases.status_paid")}</span>
                        </>
                      ) : (
                        <span>{t("purchases.status_owed", { amount: po.total_cost_dzd - (po.paid_amount_dzd || 0) })}</span>
                      )}
                    </span>
                  </td>
                  <td className="p-3 text-end space-x-2 rtl:space-x-reverse">
                    {po.status !== "received" && (
                      <button
                        type="button"
                        onClick={() => setPoToReceive(po)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold shadow hover:bg-[#02291F] transition active:scale-95"
                      >
                        <Download className="w-3.5 h-3.5 text-[#D4AF62]" />
                        <span>{t("purchases.btn_receive")}</span>
                      </button>
                    )}
                    {po.payment_status !== "paid" && (
                      <button
                        type="button"
                        onClick={() => handlePayPurchaseOrder(po.id, po.reference, po.total_cost_dzd - (po.paid_amount_dzd || 0))}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#D4AF62] text-[#02291F] font-bold shadow hover:bg-[#D4AF62]/90"
                      >
                        <CreditCard className="w-3.5 h-3.5 text-[#02291F]" />
                        <span>{t("purchases.btn_pay")}</span>
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
                    {t("purchases.modal_receive_title")}
                  </h3>
                  <p className="text-[11px] text-[#E8D4A5]/80">{t("purchases.modal_receive_sub", { ref: poToReceive.reference })}</p>
                </div>
              </div>
              <button aria-label="Fermer"
                type="button"
                onClick={() => setPoToReceive(null)}
                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-[#E8D4A5] flex items-center justify-center transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 space-y-4 text-xs">
              <p className="text-gray-700 leading-relaxed">
                {t("purchases.modal_receive_confirm")}
              </p>
              <div className="p-3.5 rounded-2xl bg-white border border-[#D4AF62]/40 space-y-1.5">
                <div className="flex justify-between text-gray-600">
                  <span>{t("purchases.modal_receive_ref")}</span>
                  <span className="font-mono font-bold text-[#063D2E]">{poToReceive.reference}</span>
                </div>
                <div className="flex justify-between text-gray-600">
                  <span>{t("purchases.modal_receive_total")}</span>
                  <span className="font-mono font-bold text-[#063D2E]">{Number(poToReceive.total_cost_dzd || 0).toLocaleString()} DA</span>
                </div>
              </div>
              <p className="text-[11px] text-emerald-800 bg-emerald-50 p-2.5 rounded-xl border border-emerald-200 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-emerald-700 shrink-0" />
                <span>{t("purchases.modal_receive_note")}</span>
              </p>
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setPoToReceive(null)}
                  disabled={receivingPo}
                  className="px-4 py-2 rounded-xl bg-gray-200 hover:bg-gray-300 text-gray-700 font-bold transition"
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="button"
                  onClick={confirmReceivePo}
                  disabled={receivingPo}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-[#063D2E] to-[#0A5C45] hover:from-[#02291F] hover:to-[#063D2E] text-[#D4AF62] font-bold shadow-md transition disabled:opacity-50"
                >
                  {receivingPo ? t("purchases.modal_receiving_btn") : t("purchases.modal_receive_btn")}
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
                    {t("purchases.modal_delete_sup_title")}
                  </h3>
                  <p className="text-[11px] text-[#E8D4A5]/80">{t("purchases.modal_delete_sup_sub")}</p>
                </div>
              </div>
              <button aria-label="Fermer"
                type="button"
                onClick={() => setSupplierToDelete(null)}
                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-[#E8D4A5] flex items-center justify-center transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 space-y-4 text-xs">
              <p className="text-gray-700 leading-relaxed">
                {t("purchases.modal_delete_sup_confirm")}
              </p>
              <div className="p-3.5 rounded-2xl bg-white border border-[#D4AF62]/40">
                <div className="font-bold text-[#063D2E] text-sm">{supplierToDelete.name}</div>
                <div className="text-[11px] text-gray-500 mt-1">Identifiant #{supplierToDelete.id}</div>
              </div>
              <p className="text-[11px] text-amber-800 bg-amber-50 p-2.5 rounded-xl border border-amber-200 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
                <span>{t("purchases.modal_delete_sup_note")}</span>
              </p>
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setSupplierToDelete(null)}
                  disabled={deletingSupplier}
                  className="px-4 py-2 rounded-xl bg-gray-200 hover:bg-gray-300 text-gray-700 font-bold transition"
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="button"
                  onClick={confirmDeleteSupplier}
                  disabled={deletingSupplier}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white font-bold shadow-md transition disabled:opacity-50"
                >
                  {deletingSupplier ? t("purchases.modal_deleting_sup_btn") : t("purchases.modal_delete_sup_btn")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {payDialog && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setPayDialog(null)}>
          <div className="bg-white rounded-3xl w-full max-w-sm p-6 shadow-2xl border-2 border-[#063D2E]/10" onClick={(e) => e.stopPropagation()}>
            <h4 className="font-bold text-[#063D2E] text-lg mb-1">{t("purchases.modal_pay_title")}</h4>
            <p className="text-sm text-gray-600 mb-4">
              {t("purchases.modal_pay_sub", { ref: payDialog.ref, amount: payDialog.amount.toLocaleString("fr-DZ") })}
            </p>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <button type="button" onClick={() => confirmPayment("cash")}
                className="h-16 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex flex-col items-center justify-center active:scale-95">
                <span className="text-lg">{t("purchases.pay_cash")}</span>
                <span className="text-[10px] font-normal opacity-70">{t("purchases.pay_cash_sub")}</span>
              </button>
              <button type="button" onClick={() => confirmPayment("bank_transfer")}
                className="h-16 rounded-2xl bg-[#D4AF62] text-[#02291F] font-bold flex flex-col items-center justify-center active:scale-95">
                <span className="text-lg">{t("purchases.pay_bank")}</span>
                <span className="text-[10px] font-normal opacity-70">{t("purchases.pay_bank_sub")}</span>
              </button>
            </div>
            <button type="button" onClick={() => setPayDialog(null)}
              className="w-full h-11 rounded-2xl bg-gray-100 text-gray-700 font-bold active:scale-95">
              {t("common.cancel")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

