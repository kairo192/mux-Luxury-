import React, { useEffect, useState, useCallback } from "react";
import {
  Truck,
  Plus,
  RefreshCw,
  Pencil,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  X,
  Phone,
  Mail,
  Package,
  Wallet,
  Archive,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";

const fmt = (dzd: number) => `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;

interface Supplier {
  id: number;
  name: string;
  company_name?: string | null;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  tax_id?: string | null;
  notes?: string | null;
  is_active: number | boolean;
  purchase_orders_count?: number;
  total_purchased_dzd?: number;
  outstanding_dzd?: number;
}

export const SuppliersPage: React.FC = () => {
  const [items, setItems] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<any | null>(null);
  const [detail, setDetail] = useState<any | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await DesktopCmsApi.listSuppliers();
      setItems(d.items || []);
      setError(null);
    } catch (e: any) {
      setError(e?.userMessage || "Chargement impossible");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const flash = (m: string) => {
    setSuccess(m);
    setError(null);
    setTimeout(() => setSuccess(null), 3500);
  };

  const openDetail = async (s: Supplier) => {
    try {
      setDetail(await DesktopCmsApi.getSupplier(s.id));
    } catch (e: any) {
      setError(e?.userMessage || "Détail indisponible");
    }
  };

  const save = async () => {
    if (!form) return;
    if (!form.name.trim()) return setError("Nom requis");
    setBusy(true);
    setError(null);
    try {
      const payload = {
        name: form.name.trim(),
        company_name: form.company_name.trim() || null,
        contact_person: form.contact_person.trim() || null,
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
        address: form.address.trim() || null,
        tax_id: form.tax_id.trim() || null,
        notes: form.notes.trim() || null,
      };
      if (form.id === null) {
        await DesktopCmsApi.createSupplier(payload);
        flash("Fournisseur créé");
      } else {
        await DesktopCmsApi.updateSupplier(form.id, payload);
        flash("Fournisseur mis à jour");
      }
      setForm(null);
      load();
    } catch (e: any) {
      setError(e?.userMessage || "Enregistrement refusé");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (s: Supplier) => {
    if (!window.confirm(`Supprimer « ${s.name} » ? Un fournisseur avec des achats sera archivé.`)) return;
    setBusy(true);
    try {
      await DesktopCmsApi.deleteSupplier(s.id);
      flash("Fournisseur supprimé ou archivé");
      load();
    } catch (e: any) {
      setError(e?.userMessage || "Suppression refusée");
    } finally {
      setBusy(false);
    }
  };

  const edit = (s: Supplier) =>
    setForm({
      id: s.id,
      name: s.name,
      company_name: s.company_name || "",
      contact_person: s.contact_person || "",
      phone: s.phone || "",
      email: s.email || "",
      address: s.address || "",
      tax_id: s.tax_id || "",
      notes: s.notes || "",
    });

  const openCreate = () =>
    setForm({ id: null, name: "", company_name: "", contact_person: "", phone: "", email: "", address: "", tax_id: "", notes: "" });

  return (
    <div className="space-y-4 text-sm">
      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" /> {error}
        </div>
      )}
      {success && (
        <div className="p-4 rounded-2xl bg-emerald-50 border-2 border-emerald-200 text-emerald-800 font-bold flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 shrink-0" /> {success}
        </div>
      )}

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
            <Truck className="w-5 h-5" /> Fournisseurs
          </h3>
          <p className="text-gray-500 mt-1">Gérez vos partenaires d'approvisionnement et suivez les montants dus.</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={load} className="h-12 w-12 rounded-2xl border-2 border-gray-200 flex items-center justify-center text-gray-500 active:scale-95">
            <RefreshCw className="w-5 h-5" />
          </button>
          <button type="button" onClick={openCreate} className="h-12 px-5 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
            <Plus className="w-5 h-5" /> Nouveau fournisseur
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> Chargement…
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white p-10 rounded-3xl border border-gray-200 text-center text-gray-400">
          Aucun fournisseur. Cliquez sur « Nouveau fournisseur ».
        </div>
      ) : (
        <div className="bg-white rounded-3xl border border-gray-200 overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-[#063D2E] text-[#E8D4A5] text-xs uppercase">
              <tr>
                <th className="px-4 py-3">Fournisseur</th>
                <th className="px-4 py-3 hidden md:table-cell">Contact</th>
                <th className="px-4 py-3 text-right">Achats</th>
                <th className="px-4 py-3 text-right">Dû</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => {
                const active = s.is_active === 1 || s.is_active === true;
                return (
                  <tr key={s.id} className={`border-t border-gray-100 hover:bg-[#FCFBF8] cursor-pointer ${!active ? "opacity-60" : ""}`} onClick={() => openDetail(s)}>
                    <td className="px-4 py-3">
                      <div className="font-bold text-[#063D2E] flex items-center gap-2">
                        {s.name}
                        {!active && <span className="text-[10px] font-bold text-gray-500 bg-gray-200 px-1.5 py-0.5 rounded"><Archive className="w-3 h-3 inline" /> archivé</span>}
                      </div>
                      {s.company_name && <div className="text-gray-500 text-[11px]">{s.company_name}</div>}
                      {s.tax_id && <div className="text-gray-400 font-mono text-[11px]">NIF: {s.tax_id}</div>}
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell text-gray-500">
                      {s.contact_person && <div>{s.contact_person}</div>}
                      {s.phone && <div className="font-mono text-[11px]">{s.phone}</div>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="font-mono font-bold">{fmt(s.total_purchased_dzd || 0)}</div>
                      <div className="text-[11px] text-gray-400">{s.purchase_orders_count || 0} BC</div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={`font-mono font-bold ${(s.outstanding_dzd || 0) > 0 ? "text-amber-700" : "text-gray-400"}`}>
                        {(s.outstanding_dzd || 0) > 0 ? fmt(s.outstanding_dzd || 0) : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex gap-1.5 justify-end">
                        <button type="button" onClick={() => edit(s)} className="h-10 w-10 rounded-xl border-2 border-gray-200 inline-flex items-center justify-center text-gray-500 active:scale-95">
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button type="button" onClick={() => remove(s)} className="h-10 w-10 rounded-xl border-2 border-red-200 inline-flex items-center justify-center text-red-500 active:scale-95">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* DETAIL MODAL */}
      {detail && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setDetail(null)}>
          <div className="bg-white rounded-3xl w-full max-w-lg max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <div>
                <h3 className="font-serif font-bold text-[#063D2E] text-lg">{detail.name}</h3>
                <div className="text-gray-500 text-[11px] flex items-center gap-3 flex-wrap">
                  {detail.contact_person && <span>{detail.contact_person}</span>}
                  {detail.phone && <span className="flex items-center gap-1 font-mono"><Phone className="w-3 h-3" /> {detail.phone}</span>}
                  {detail.email && <span className="flex items-center gap-1 font-mono"><Mail className="w-3 h-3" /> {detail.email}</span>}
                </div>
              </div>
              <button type="button" onClick={() => setDetail(null)} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <Kpi icon={Package} label="Bons" value={String(detail.stats.purchase_orders_count)} sub="de commande" />
                <Kpi icon={Wallet} label="Acheté" value={fmt(detail.stats.total_purchased_dzd)} sub="total" />
                <Kpi icon={Wallet} label="Dû" value={fmt(detail.stats.outstanding_dzd)} sub="restant" accent={detail.stats.outstanding_dzd > 0} />
              </div>
              {detail.notes && <div className="p-3 rounded-2xl bg-[#F5F3EE] text-gray-600">{detail.notes}</div>}
              <div>
                <h4 className="font-bold text-[#063D2E] mb-2">Bons de commande récents</h4>
                <div className="space-y-1 max-h-60 overflow-auto">
                  {detail.recent_purchase_orders.length === 0 && <div className="text-gray-400">Aucun bon de commande.</div>}
                  {detail.recent_purchase_orders.map((po: any) => {
                    const owed = (po.total_cost_dzd || 0) - (po.paid_amount_dzd || 0);
                    return (
                      <div key={po.id} className="flex items-center justify-between p-2 rounded-xl border border-gray-100">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold">{po.reference}</span>
                          <span className="text-[10px] font-bold text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">{po.status}</span>
                          <span className="text-[11px] text-gray-400">{new Date(po.created_at).toLocaleDateString("fr-DZ")}</span>
                        </div>
                        <div className="text-right">
                          <div className="font-mono font-bold">{fmt(po.total_cost_dzd)}</div>
                          {owed > 0 && <div className="text-[11px] text-amber-700 font-mono">dû {fmt(owed)}</div>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CREATE/EDIT MODAL */}
      {form && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setForm(null)}>
          <div className="bg-white rounded-3xl w-full max-w-md max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <h3 className="font-serif font-bold text-[#063D2E] text-lg">{form.id === null ? "Nouveau fournisseur" : "Modifier le fournisseur"}</h3>
              <button type="button" onClick={() => setForm(null)} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-5 space-y-3">
              <Input label="Nom" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
              <div className="grid grid-cols-2 gap-3">
                <Input label="Raison sociale" value={form.company_name} onChange={(v) => setForm({ ...form, company_name: v })} />
                <Input label="Contact" value={form.contact_person} onChange={(v) => setForm({ ...form, contact_person: v })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Input label="Téléphone" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} mono />
                <Input label="E-mail" value={form.email} onChange={(v) => setForm({ ...form, email: v })} mono />
              </div>
              <Input label="Adresse" value={form.address} onChange={(v) => setForm({ ...form, address: v })} />
              <Input label="NIF / Identifiant fiscal" value={form.tax_id} onChange={(v) => setForm({ ...form, tax_id: v })} mono />
              <label className="block">
                <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">Notes</span>
                <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} className="w-full px-3 py-2 rounded-2xl border-2 border-gray-200" />
              </label>
              <button type="button" disabled={busy} onClick={save} className="w-full h-14 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-base disabled:opacity-50 active:scale-[0.99]">
                {form.id === null ? "Créer" : "Enregistrer"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Input: React.FC<{ label: string; value: string; onChange: (v: string) => void; mono?: boolean }> = ({ label, value, onChange, mono }) => (
  <label className="block">
    <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{label}</span>
    <input value={value} onChange={(e) => onChange(e.target.value)} className={`w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none ${mono ? "font-mono" : ""}`} />
  </label>
);

const Kpi: React.FC<{ icon: any; label: string; value: string; sub: string; accent?: boolean }> = ({ icon: Icon, label, value, sub, accent }) => (
  <div className={`p-3 rounded-2xl border text-center ${accent ? "border-amber-300 bg-amber-50" : "border-gray-200"}`}>
    <div className="flex items-center justify-center gap-1 text-gray-500 text-[11px] font-bold uppercase"><Icon className="w-3.5 h-3.5" /> {label}</div>
    <div className={`text-base font-extrabold font-mono tabular-nums mt-0.5 ${accent ? "text-amber-700" : "text-[#063D2E]"}`}>{value}</div>
    <div className="text-[10px] text-gray-400">{sub}</div>
  </div>
);
