import React, { useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Layers,
  Plus,
  RefreshCw,
  Save,
  SlidersHorizontal,
  Trash2,
  X,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { notifyClientError, notifyClientSuccess, notifyClientWarning } from "../utils/clientNotifier";

// ============================================================================
// REAL VARIANT MANAGER — colour / size / custom axis combinations
// Works in two modes:
//  * create mode (no productId): combinations are built locally and submitted
//    together with the product, so a new article is born with its variants.
//  * edit mode (productId): every change hits the server immediately through
//    /admin/products/{id}/variants, /admin/variants/{id} and the bulk endpoint.
// ============================================================================

export type VariantAxisOption = {
  id?: number;
  value: string;
  label_fr?: string;
  color_hex?: string | null;
};

export type VariantAxis = {
  id?: number;
  attr_key: string;
  label_fr: string;
  input_type?: string;
  is_variant_axis?: boolean;
  options?: VariantAxisOption[];
};

export type EditorVariant = {
  id?: number;
  sku: string;
  title: string;
  stock_qty: number;
  price_override_dzd?: number | null;
  barcode?: string | null;
  low_stock_threshold?: number;
  is_active?: boolean;
  is_low_stock?: boolean;
  effective_price_dzd?: number;
  attributes: Record<string, string>;
  /** local-only marker so the CMS can flag what still has to be created */
  __new?: boolean;
};

type Props = {
  productId?: number | null;
  productSku: string;
  productPrice: number;
  axes: VariantAxis[];
  variants: EditorVariant[];
  onChange?: (variants: EditorVariant[]) => void;
  onRefresh?: () => void | Promise<void>;
};

function badgeColor(value: string, axis?: VariantAxis) {
  const hex = (axis?.options || []).find((o) => o.value === value)?.color_hex;
  return hex || null;
}

function signatureOf(attrs: Record<string, string>) {
  return Object.keys(attrs)
    .sort()
    .map((k) => `${k}:${attrs[k]}`)
    .join("|");
}

function autoSku(productSku: string, attrs: Record<string, string>) {
  const base = (productSku || "LUX").replace(/\s+/g, "-").toUpperCase();
  const parts = Object.keys(attrs)
    .sort()
    .map((k) => String(attrs[k]).normalize("NFD").replace(/[^A-Za-z0-9]/g, "").toUpperCase().slice(0, 4) || "X");
  return parts.length ? `${base}-${parts.join("-")}` : `${base}-STD`;
}

export function VariantManager({
  productId,
  productSku,
  productPrice,
  axes,
  variants,
  onChange,
  onRefresh,
}: Props) {
  const isCreateMode = !productId;
  const [selection, setSelection] = useState<Record<string, string[]>>(() => {
    const seeded: Record<string, string[]> = {};
    axes.forEach((axis) => {
      const used = Array.from(
        new Set(variants.map((v) => v.attributes?.[axis.attr_key]).filter(Boolean))
      ) as string[];
      seeded[axis.attr_key] = used.length ? used : (axis.options || []).slice(0, 1).map((o) => o.value);
    });
    return seeded;
  });
  const [customValue, setCustomValue] = useState<Record<string, string>>({});
  const [defaultStock, setDefaultStock] = useState(3);
  const [defaultThreshold, setDefaultThreshold] = useState(3);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [rowEdits, setRowEdits] = useState<Record<number, Partial<EditorVariant>>>({});
  const [showAddForm, setShowAddForm] = useState(false);
  const [newVariant, setNewVariant] = useState<{ stock: number; price: string; sku: string; attrs: Record<string, string> }>({
    stock: 0,
    price: "",
    sku: "",
    attrs: {},
  });

  const existingSignatures = useMemo(
    () => new Set(variants.map((v) => signatureOf(v.attributes || {}))),
    [variants]
  );

  const combos = useMemo(() => {
    const activeAxes = axes.filter((a) => (selection[a.attr_key] || []).length > 0);
    if (!activeAxes.length) return [] as Array<Record<string, string>>;
    let acc: Array<Record<string, string>> = [{}];
    activeAxes.forEach((axis) => {
      const values = selection[axis.attr_key] || [];
      const next: Array<Record<string, string>> = [];
      acc.forEach((partial) => {
        values.forEach((val) => next.push({ ...partial, [axis.attr_key]: val }));
      });
      acc = next;
    });
    return acc;
  }, [axes, selection]);

  const missingCombos = combos.filter((c) => !existingSignatures.has(signatureOf(c)));

  const totalStock = variants.reduce((sum, v) => sum + Number(v.stock_qty || 0), 0);
  const outOfStock = variants.filter((v) => Number(v.stock_qty || 0) <= 0).length;
  const lowStock = variants.filter(
    (v) => Number(v.stock_qty || 0) > 0 && Number(v.stock_qty || 0) <= Number(v.low_stock_threshold ?? 3)
  ).length;

  function toggleValue(axisKey: string, value: string) {
    setSelection((prev) => {
      const current = prev[axisKey] || [];
      const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
      return { ...prev, [axisKey]: next };
    });
  }

  function addCustomValue(axisKey: string) {
    const value = (customValue[axisKey] || "").trim();
    if (!value) return;
    setSelection((prev) => ({
      ...prev,
      [axisKey]: Array.from(new Set([...(prev[axisKey] || []), value])),
    }));
    setCustomValue((prev) => ({ ...prev, [axisKey]: "" }));
  }

  function buildDraftCombos() {
    if (!combos.length) {
      notifyClientWarning("Aucune combinaison", "Sélectionnez au moins une valeur sur chaque axe de déclinaison.");
      return;
    }
    if (isCreateMode) {
      const additions: EditorVariant[] = missingCombos.map((attrs) => ({
        sku: autoSku(productSku, attrs),
        title: axes
          .filter((a) => attrs[a.attr_key])
          .map((a) => attrs[a.attr_key])
          .join(" / "),
        stock_qty: defaultStock,
        price_override_dzd: null,
        low_stock_threshold: defaultThreshold,
        is_active: true,
        attributes: attrs,
        __new: true,
      }));
      if (!additions.length) {
        notifyClientWarning("Déclinaisons déjà présentes", "Toutes les combinaisons sélectionnées existent déjà dans le brouillon.");
        return;
      }
      onChange?.([...variants, ...additions]);
      notifyClientSuccess("Déclinaisons ajoutées", `${additions.length} combinaison(s) ajoutée(s) au brouillon du produit.`);
    }
  }

  async function generateMatrixOnServer() {
    if (!productId) return;
    const activeAxes = axes.filter((a) => (selection[a.attr_key] || []).length > 0);
    if (!activeAxes.length) {
      notifyClientWarning("Axes requis", "Sélectionnez au moins une valeur sur un axe de déclinaison.");
      return;
    }
    setBusy(true);
    try {
      const payloadAxes: Record<string, string[]> = {};
      activeAxes.forEach((a) => {
        payloadAxes[a.attr_key] = selection[a.attr_key];
      });
      const res = await DesktopCmsApi.generateVariants(productId, {
        axes: payloadAxes,
        default_stock: defaultStock,
        low_stock_threshold: defaultThreshold,
      });
      const created = res?.created_count ?? res?.created?.length ?? 0;
      const skipped = res?.skipped_duplicates ?? 0;
      notifyClientSuccess(
        "Matrice de déclinaisons générée",
        `${created} variante(s) créée(s)${skipped ? `, ${skipped} déjà existante(s) ignorée(s)` : ""}.`
      );
      await onRefresh?.();
    } catch (err: any) {
      notifyClientError(err, "Génération de la matrice impossible");
    } finally {
      setBusy(false);
    }
  }

  async function addSingleVariant() {
    const attrs: Record<string, string> = {};
    Object.entries(newVariant.attrs).forEach(([k, v]) => {
      if (v) attrs[k] = v;
    });
    if (axes.length > 0 && Object.keys(attrs).length === 0) {
      notifyClientWarning("Déclinaison incomplète", "Choisissez une valeur pour chaque axe de déclinaison.");
      return;
    }
    const sig = signatureOf(attrs);
    if (existingSignatures.has(sig)) {
      notifyClientWarning("Combinaison existante", "Cette combinaison couleur/taille existe déjà pour ce produit.");
      return;
    }
    setBusy(true);
    try {
      if (isCreateMode) {
        onChange?.([
          ...variants,
          {
            sku: (newVariant.sku || autoSku(productSku, attrs)).trim(),
            title: axes
              .filter((a) => attrs[a.attr_key])
              .map((a) => attrs[a.attr_key])
              .join(" / ") || "Standard",
            stock_qty: Number(newVariant.stock) || 0,
            price_override_dzd: newVariant.price === "" ? null : Number(newVariant.price),
            low_stock_threshold: defaultThreshold,
            is_active: true,
            attributes: attrs,
            __new: true,
          },
        ]);
        notifyClientSuccess("Déclinaison ajoutée", "La combinaison sera enregistrée avec le produit.");
      } else {
        await DesktopCmsApi.createVariant(productId!, {
          sku: newVariant.sku.trim() || undefined,
          stock_qty: Number(newVariant.stock) || 0,
          price_override_dzd: newVariant.price === "" ? null : Number(newVariant.price),
          low_stock_threshold: defaultThreshold,
          is_active: true,
          attributes: attrs,
        });
        notifyClientSuccess("Déclinaison créée", "La nouvelle combinaison est disponible sur la boutique.");
        await onRefresh?.();
      }
      setNewVariant({ stock: 0, price: "", sku: "", attrs: {} });
      setShowAddForm(false);
    } catch (err: any) {
      notifyClientError(err, "Création de la déclinaison refusée");
    } finally {
      setBusy(false);
    }
  }

  async function saveRowEdits() {
    if (isCreateMode) {
      const merged = variants.map((v, idx) => {
        const edit = v.id ? rowEdits[v.id] : undefined;
        return edit ? { ...v, ...edit } : v;
      });
      onChange?.(merged);
      setRowEdits({});
      notifyClientSuccess("Brouillon mis à jour", "Les valeurs seront enregistrées avec le produit.");
      return;
    }
    const entries = Object.entries(rowEdits);
    if (!entries.length) return;
    setBusy(true);
    let ok = 0;
    const failures: string[] = [];
    for (const [idStr, patch] of entries) {
      const variantId = Number(idStr);
      const payload: Record<string, unknown> = {};
      if (patch.stock_qty !== undefined) payload.stock_qty = Number(patch.stock_qty);
      if (patch.sku !== undefined) payload.sku = String(patch.sku).trim();
      if (patch.barcode !== undefined) payload.barcode = patch.barcode ? String(patch.barcode).trim() : "";
      if (patch.low_stock_threshold !== undefined) payload.low_stock_threshold = Number(patch.low_stock_threshold);
      if (patch.is_active !== undefined) payload.is_active = Boolean(patch.is_active);
      if (patch.price_override_dzd !== undefined) {
        if (patch.price_override_dzd === null || String(patch.price_override_dzd) === "") {
          payload.clear_price_override = true;
        } else {
          payload.price_override_dzd = Number(patch.price_override_dzd);
        }
      }
      try {
        await DesktopCmsApi.updateVariant(variantId, payload);
        ok += 1;
      } catch (err: any) {
        const tr = notifyClientError(err, `Déclinaison #${variantId} refusée`, false);
        failures.push(`#${variantId}: ${tr.message}`);
      }
    }
    setBusy(false);
    if (ok) {
      notifyClientSuccess("Déclinaisons enregistrées", `${ok} variante(s) mise(s) à jour sur le serveur.`);
      setRowEdits({});
      await onRefresh?.();
    }
    if (failures.length) {
      notifyClientError(new Error(failures.join(" · ")), "Certaines déclinaisons n'ont pas pu être enregistrées");
    }
  }

  async function removeVariant(variant: EditorVariant) {
    if (isCreateMode) {
      onChange?.(variants.filter((v) => v !== variant));
      return;
    }
    if (!variant.id) return;
    setBusy(true);
    try {
      const res = await DesktopCmsApi.deleteVariant(variant.id);
      if (res?.deactivated) {
        notifyClientWarning(
          "Déclinaison désactivée",
          res.reason || "Cette variante est liée à des commandes : elle a été désactivée au lieu d'être supprimée."
        );
      } else {
        notifyClientSuccess("Déclinaison supprimée", `SKU ${variant.sku} retiré du catalogue.`);
      }
      await onRefresh?.();
    } catch (err: any) {
      notifyClientError(err, "Suppression de la déclinaison impossible");
    } finally {
      setBusy(false);
    }
  }

  async function runBulk(action: "stock" | "price" | "clear_price" | "activate" | "deactivate") {
    if (!selectedIds.length) {
      notifyClientWarning("Sélection vide", "Sélectionnez au moins une déclinaison.");
      return;
    }
    const payload: any = { variant_ids: selectedIds, reason: `cms_bulk_${action}` };
    if (action === "stock") {
      const raw = window.prompt("Nouveau stock pour les déclinaisons sélectionnées :", String(defaultStock));
      if (raw === null) return;
      const qty = Number(raw);
      if (!Number.isFinite(qty) || qty < 0) {
        notifyClientWarning("Quantité invalide", "Le stock doit être un nombre entier positif ou nul.");
        return;
      }
      payload.set_stock_qty = Math.floor(qty);
    }
    if (action === "price") {
      const raw = window.prompt("Prix spécifique en DA (laisser vide pour annuler) :", String(productPrice));
      if (raw === null) return;
      const price = Number(raw);
      if (!Number.isFinite(price) || price < 0) {
        notifyClientWarning("Prix invalide", "Le prix doit être un nombre positif ou nul.");
        return;
      }
      payload.set_price_override_dzd = Math.floor(price);
    }
    if (action === "clear_price") payload.clear_price_override = true;
    if (action === "activate") payload.is_active = true;
    if (action === "deactivate") payload.is_active = false;

    setBusy(true);
    try {
      const res = await DesktopCmsApi.bulkUpdateVariants(payload);
      notifyClientSuccess(
        "Action groupée appliquée",
        `${res.updated_count} déclinaison(s) mise(s) à jour${res.missing_ids?.length ? `, ${res.missing_ids.length} introuvable(s)` : ""}.`
      );
      setSelectedIds([]);
      setRowEdits({});
      await onRefresh?.();
    } catch (err: any) {
      notifyClientError(err, "Action groupée refusée");
    } finally {
      setBusy(false);
    }
  }

  const dirtyCount = Object.keys(rowEdits).length;

  if (!axes.length) {
    return (
      <div className="p-6 rounded-2xl bg-[#F8F6F0] border border-[#D4AF62]/40 text-xs space-y-2">
        <p className="font-bold text-[#063D2E] flex items-center gap-2">
          <Layers className="w-4 h-4" /> Déclinaisons (couleurs / tailles)
        </p>
        <p className="text-gray-600 leading-relaxed">
          Cette catégorie ne définit aucun axe de déclinaison. Le produit sera vendu en référence unique avec son stock global.
        </p>
        <p className="text-[11px] text-gray-500">
          Pour proposer plusieurs couleurs ou pointures, activez l'option « Axe de déclinaison » sur un attribut dans l'onglet
          <span className="font-bold"> Catégories</span>.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4 text-xs">
      {/* Combination builder */}
      <div className="p-4 rounded-2xl bg-[#F8F6F0] border border-[#D4AF62]/40 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-bold text-[#063D2E] flex items-center gap-2">
            <SlidersHorizontal className="w-4 h-4 text-[#063D2E]" />
            <span>Combinaisons vendables</span>
          </p>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1 text-[11px] font-semibold text-gray-600">
              Stock par défaut
              <input
                type="number"
                min={0}
                value={defaultStock}
                onChange={(e) => setDefaultStock(Math.max(0, Number(e.target.value)))}
                className="w-16 px-2 py-1 border rounded-lg bg-white font-mono"
              />
            </label>
            <label className="flex items-center gap-1 text-[11px] font-semibold text-gray-600">
              Seuil alerte
              <input
                type="number"
                min={0}
                value={defaultThreshold}
                onChange={(e) => setDefaultThreshold(Math.max(0, Number(e.target.value)))}
                className="w-16 px-2 py-1 border rounded-lg bg-white font-mono"
              />
            </label>
          </div>
        </div>

        {axes.map((axis) => (
          <div key={axis.attr_key} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-[11px] uppercase tracking-wide text-gray-500">{axis.label_fr}</span>
              <span className="text-[10px] text-gray-400 font-mono">{axis.attr_key}</span>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              {(axis.options || []).map((opt) => {
                const active = (selection[axis.attr_key] || []).includes(opt.value);
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => toggleValue(axis.attr_key, opt.value)}
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border font-semibold transition ${
                      active
                        ? "bg-[#063D2E] text-[#E8D4A5] border-[#063D2E] shadow-xs"
                        : "bg-white text-gray-700 border-gray-300 hover:border-[#063D2E]"
                    }`}
                  >
                    {opt.color_hex && (
                      <span
                        className="w-3 h-3 rounded-full border border-white/60 shadow-xs"
                        style={{ backgroundColor: opt.color_hex }}
                      />
                    )}
                    <span>{opt.label_fr || opt.value}</span>
                    {active && <Check className="w-3 h-3" />}
                  </button>
                );
              })}
              {(selection[axis.attr_key] || [])
                .filter((v) => !(axis.options || []).some((o) => o.value === v))
                .map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => toggleValue(axis.attr_key, v)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border font-semibold bg-amber-50 text-amber-900 border-amber-300"
                    title="Valeur personnalisée (sera ajoutée à la bibliothèque d'options)"
                  >
                    <span>{v}</span>
                    <X className="w-3 h-3" />
                  </button>
                ))}
              <div className="flex items-center gap-1">
                <input
                  value={customValue[axis.attr_key] || ""}
                  onChange={(e) => setCustomValue((p) => ({ ...p, [axis.attr_key]: e.target.value }))}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addCustomValue(axis.attr_key);
                    }
                  }}
                  placeholder="Autre valeur…"
                  className="w-28 px-2 py-1 border border-dashed rounded-lg bg-white"
                />
                <button
                  type="button"
                  onClick={() => addCustomValue(axis.attr_key)}
                  className="px-2 py-1 rounded-lg bg-white border border-[#D4AF62] font-bold text-[#063D2E]"
                  title="Ajouter cette valeur personnalisée"
                >
                  <Plus className="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>
        ))}

        <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-[#D4AF62]/20">
          <span className="text-[11px] text-gray-600">
            {combos.length} combinaison(s) théorique(s) · <strong className="text-emerald-700">{variants.length}</strong>{" "}
            existante(s) ·{" "}
            <strong className={missingCombos.length ? "text-amber-700" : "text-gray-500"}>
              {missingCombos.length} manquante(s)
            </strong>
          </span>
          <div className="flex-1" />
          {isCreateMode ? (
            <button
              type="button"
              onClick={buildDraftCombos}
              disabled={!missingCombos.length}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Ajouter {missingCombos.length || ""} combinaison(s)</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={generateMatrixOnServer}
              disabled={busy || !missingCombos.length}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {busy ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Layers className="w-3.5 h-3.5" />}
              <span>Générer les {missingCombos.length || ""} manquantes</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowAddForm((s) => !s)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-[#063D2E] text-[#063D2E] font-bold"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Déclinaison manuelle</span>
          </button>
        </div>

        {showAddForm && (
          <div className="p-3 rounded-xl bg-white border border-[#D4AF62]/50 space-y-2">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              {axes.map((axis) => (
                <div key={axis.attr_key}>
                  <label className="block font-semibold mb-1">{axis.label_fr}</label>
                  <select
                    value={newVariant.attrs[axis.attr_key] || ""}
                    onChange={(e) =>
                      setNewVariant((prev) => ({ ...prev, attrs: { ...prev.attrs, [axis.attr_key]: e.target.value } }))
                    }
                    className="w-full px-2 py-1.5 border rounded-lg bg-white"
                  >
                    <option value="">— Choisir —</option>
                    {(axis.options || []).map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label_fr || o.value}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
              <div>
                <label className="block font-semibold mb-1">Stock</label>
                <input
                  type="number"
                  min={0}
                  value={newVariant.stock}
                  onChange={(e) => setNewVariant((prev) => ({ ...prev, stock: Number(e.target.value) }))}
                  className="w-full px-2 py-1.5 border rounded-lg bg-white font-mono"
                />
              </div>
              <div>
                <label className="block font-semibold mb-1">Prix spécifique (DA)</label>
                <input
                  type="number"
                  min={0}
                  value={newVariant.price}
                  onChange={(e) => setNewVariant((prev) => ({ ...prev, price: e.target.value }))}
                  placeholder={`Défaut : ${productPrice.toLocaleString()}`}
                  className="w-full px-2 py-1.5 border rounded-lg bg-white font-mono"
                />
              </div>
              <div>
                <label className="block font-semibold mb-1">SKU (auto si vide)</label>
                <input
                  value={newVariant.sku}
                  onChange={(e) => setNewVariant((prev) => ({ ...prev, sku: e.target.value }))}
                  className="w-full px-2 py-1.5 border rounded-lg bg-white font-mono uppercase"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={addSingleVariant}
                disabled={busy}
                className="px-3 py-1.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-extrabold disabled:opacity-50"
              >
                Ajouter la déclinaison
              </button>
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-3 py-1.5 rounded-lg bg-gray-100 font-bold text-gray-700"
              >
                Annuler
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Variants table */}
      <div className="rounded-2xl border border-[#D4AF62]/40 bg-white overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 bg-[#063D2E] text-[#E8D4A5]">
          <div className="flex items-center gap-3 font-bold">
            <Layers className="w-4 h-4" />
            <span>{variants.length} déclinaison(s)</span>
            <span className="text-[11px] font-normal text-[#E8D4A5]/80">
              Stock total : {totalStock} · Rupture : {outOfStock} · Alerte : {lowStock}
            </span>
          </div>
          {dirtyCount > 0 && (
            <button
              type="button"
              onClick={saveRowEdits}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold disabled:opacity-50"
            >
              <Save className="w-3.5 h-3.5" />
              <span>Enregistrer {dirtyCount} modification(s)</span>
            </button>
          )}
        </div>

        {selectedIds.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 px-4 py-2 bg-[#F8F6F0] border-b border-[#D4AF62]/30">
            <span className="font-bold text-[#063D2E]">{selectedIds.length} sélectionnée(s) :</span>
            <button type="button" onClick={() => runBulk("stock")} className="px-2.5 py-1 rounded-lg bg-white border border-[#063D2E] font-bold text-[#063D2E]">
              Définir le stock
            </button>
            <button type="button" onClick={() => runBulk("price")} className="px-2.5 py-1 rounded-lg bg-white border border-[#063D2E] font-bold text-[#063D2E]">
              Définir le prix
            </button>
            <button type="button" onClick={() => runBulk("clear_price")} className="px-2.5 py-1 rounded-lg bg-white border border-gray-300 font-bold text-gray-700">
              Prix produit
            </button>
            <button type="button" onClick={() => runBulk("activate")} className="px-2.5 py-1 rounded-lg bg-emerald-50 border border-emerald-300 font-bold text-emerald-800">
              Activer
            </button>
            <button type="button" onClick={() => runBulk("deactivate")} className="px-2.5 py-1 rounded-lg bg-amber-50 border border-amber-300 font-bold text-amber-800">
              Désactiver
            </button>
            <button type="button" onClick={() => setSelectedIds([])} className="ml-auto p-1 rounded text-gray-500 hover:text-black">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {variants.length === 0 ? (
          <div className="p-8 text-center space-y-2">
            <PackageIcon />
            <p className="font-bold text-gray-700">Aucune déclinaison enregistrée</p>
            <p className="text-gray-500 max-w-md mx-auto">
              Sélectionnez les couleurs et tailles ci-dessus puis cliquez sur « Ajouter les combinaisons » pour créer les
              références vendables.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#F8F6F0] text-[#063D2E] text-[11px] uppercase tracking-wide">
                  <th className="p-2 w-8">
                    <input
                      type="checkbox"
                      checked={selectedIds.length === variants.filter((v) => v.id).length && selectedIds.length > 0}
                      onChange={(e) =>
                        setSelectedIds(e.target.checked ? variants.filter((v) => v.id).map((v) => v.id!) : [])
                      }
                      className="w-3.5 h-3.5"
                      disabled={isCreateMode}
                    />
                  </th>
                  <th className="p-2">Déclinaison</th>
                  <th className="p-2">SKU</th>
                  <th className="p-2">Code-barres</th>
                  <th className="p-2 text-right">Prix</th>
                  <th className="p-2 text-center">Stock</th>
                  <th className="p-2 text-center">Seuil</th>
                  <th className="p-2 text-center">État</th>
                  <th className="p-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {variants.map((variant, idx) => {
                  const key = variant.id ?? `draft-${idx}`;
                  const edit = variant.id ? rowEdits[variant.id] || {} : {};
                  const value = <K extends keyof EditorVariant>(field: K): any =>
                    edit[field] !== undefined ? edit[field] : variant[field];
                  const attrs = variant.attributes || {};
                  const isDirty = variant.id ? Boolean(rowEdits[variant.id]) : false;
                  return (
                    <tr key={key} className={isDirty ? "bg-amber-50/60" : "hover:bg-gray-50/70"}>
                      <td className="p-2 text-center">
                        <input
                          type="checkbox"
                          disabled={isCreateMode || !variant.id}
                          checked={Boolean(variant.id && selectedIds.includes(variant.id))}
                          onChange={(e) => {
                            if (!variant.id) return;
                            setSelectedIds((prev) =>
                              e.target.checked ? [...prev, variant.id!] : prev.filter((id) => id !== variant.id)
                            );
                          }}
                          className="w-3.5 h-3.5"
                        />
                      </td>
                      <td className="p-2">
                        <div className="flex flex-wrap items-center gap-1">
                          {axes.map((axis) => {
                            const val = attrs[axis.attr_key];
                            if (!val) return null;
                            const hex = badgeColor(val, axis);
                            return (
                              <span
                                key={axis.attr_key}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#F8F6F0] border border-[#D4AF62]/40 font-semibold text-[11px]"
                                title={axis.label_fr}
                              >
                                {hex && <span className="w-2.5 h-2.5 rounded-full border border-white" style={{ backgroundColor: hex }} />}
                                {val}
                              </span>
                            );
                          })}
                          {variant.__new && (
                            <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 text-[10px] font-bold">
                              NON ENREGISTRÉE
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-gray-400 mt-0.5">{variant.title}</div>
                      </td>
                      <td className="p-2">
                        <input
                          value={String(value("sku") ?? "")}
                          onChange={(e) => {
                            if (isCreateMode) {
                              onChange?.(variants.map((v, i) => (i === idx ? { ...v, sku: e.target.value } : v)));
                            } else if (variant.id) {
                              setRowEdits((prev) => ({ ...prev, [variant.id!]: { ...prev[variant.id!], sku: e.target.value } }));
                            }
                          }}
                          className="w-40 px-2 py-1 border rounded-lg font-mono uppercase bg-white"
                        />
                      </td>
                      <td className="p-2">
                        <input
                          value={String(value("barcode") ?? "")}
                          onChange={(e) => {
                            if (variant.id) {
                              setRowEdits((prev) => ({
                                ...prev,
                                [variant.id!]: { ...prev[variant.id!], barcode: e.target.value },
                              }));
                            }
                          }}
                          placeholder="—"
                          className="w-28 px-2 py-1 border rounded-lg font-mono bg-white"
                        />
                      </td>
                      <td className="p-2 text-right">
                        <input
                          type="number"
                          min={0}
                          value={value("price_override_dzd") === null || value("price_override_dzd") === undefined ? "" : Number(value("price_override_dzd"))}
                          placeholder={String(productPrice)}
                          onChange={(e) => {
                            const raw = e.target.value;
                            const patch = { price_override_dzd: raw === "" ? null : Number(raw) };
                            if (isCreateMode) {
                              onChange?.(variants.map((v, i) => (i === idx ? { ...v, ...patch } : v)));
                            } else if (variant.id) {
                              setRowEdits((prev) => ({ ...prev, [variant.id!]: { ...prev[variant.id!], ...patch } }));
                            }
                          }}
                          className="w-24 px-2 py-1 border rounded-lg font-mono text-right bg-white"
                        />
                        <div className="text-[10px] text-gray-500 font-mono">
                          {(value("price_override_dzd") === null || value("price_override_dzd") === undefined
                            ? productPrice
                            : Number(value("price_override_dzd"))
                          ).toLocaleString()}{" "}
                          DA
                        </div>
                      </td>
                      <td className="p-2 text-center">
                        <input
                          type="number"
                          min={0}
                          value={Number(value("stock_qty") ?? 0)}
                          onChange={(e) => {
                            const qty = Math.max(0, Number(e.target.value) || 0);
                            if (isCreateMode) {
                              onChange?.(variants.map((v, i) => (i === idx ? { ...v, stock_qty: qty } : v)));
                            } else if (variant.id) {
                              setRowEdits((prev) => ({ ...prev, [variant.id!]: { ...prev[variant.id!], stock_qty: qty } }));
                            }
                          }}
                          className={`w-20 px-2 py-1 border rounded-lg font-mono text-center bg-white ${
                            Number(value("stock_qty") ?? 0) <= 0 ? "border-rose-300 text-rose-700 font-bold" : ""
                          }`}
                        />
                      </td>
                      <td className="p-2 text-center">
                        <input
                          type="number"
                          min={0}
                          value={Number(value("low_stock_threshold") ?? 3)}
                          onChange={(e) => {
                            const threshold = Math.max(0, Number(e.target.value) || 0);
                            if (variant.id) {
                              setRowEdits((prev) => ({
                                ...prev,
                                [variant.id!]: { ...prev[variant.id!], low_stock_threshold: threshold },
                              }));
                            }
                          }}
                          className="w-16 px-2 py-1 border rounded-lg font-mono text-center bg-white"
                        />
                      </td>
                      <td className="p-2 text-center">
                        {Number(value("stock_qty") ?? 0) <= 0 ? (
                          <span className="px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 font-bold text-[10px]">
                            Rupture
                          </span>
                        ) : Number(value("stock_qty") ?? 0) <= Number(value("low_stock_threshold") ?? 3) ? (
                          <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-300 font-bold text-[10px]">
                            Faible
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 font-bold text-[10px]">
                            Disponible
                          </span>
                        )}
                        {variant.is_active === false && (
                          <div className="text-[10px] text-gray-500 font-bold mt-0.5">Inactif</div>
                        )}
                      </td>
                      <td className="p-2 text-right whitespace-nowrap space-x-1">
                        {!isCreateMode && variant.id && (
                          <button
                            type="button"
                            onClick={() =>
                              setRowEdits((prev) => ({
                                ...prev,
                                [variant.id!]: { ...prev[variant.id!], is_active: !(variant.is_active !== false) },
                              }))
                            }
                            className={`px-2 py-1 rounded-lg border font-bold ${
                              (edit.is_active !== undefined ? edit.is_active : variant.is_active !== false)
                                ? "bg-white border-gray-300 text-gray-700"
                                : "bg-amber-50 border-amber-300 text-amber-800"
                            }`}
                            title="Activer / désactiver la déclinaison sur la boutique"
                          >
                            {edit.is_active !== undefined ? (edit.is_active ? "Activer" : "Désactiver") : variant.is_active !== false ? "Désactiver" : "Activer"}
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => removeVariant(variant)}
                          className="px-2 py-1 rounded-lg bg-red-50 border border-red-200 text-red-700 font-bold"
                          title="Supprimer la déclinaison"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <p className="flex items-start gap-1.5 text-[11px] text-gray-500">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
        <span>
          Une déclinaison liée à des commandes passées ne peut pas être supprimée définitivement : elle est automatiquement
          désactivée pour préserver l'historique. Le prix affiché sur la boutique est toujours recalculé côté serveur.
        </span>
      </p>
    </div>
  );
}

function PackageIcon() {
  return (
    <div className="w-12 h-12 rounded-2xl bg-[#F8F6F0] border border-[#D4AF62]/40 flex items-center justify-center mx-auto text-[#063D2E]">
      <CheckCircle2 className="w-6 h-6" />
    </div>
  );
}
